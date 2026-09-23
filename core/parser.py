"""
Page-by-Page Academic PDF Parser with Flawless Vector SVG Math Rendering & Universal Template Compatibility
Robustly handles diverse academic conference formats (COLM, ICLR, NeurIPS, ACL, IEEE, ACM) and LLM benchmark notation (Pass@k).
"""

import os
import re
from typing import Dict, Any, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from core.visual_highlighter import VisualHighlighter

class PaperPDFParser:
    """Extracts clean body blocks, synchronized bounding boxes, and performs cross-page sentence stitching."""

    @classmethod
    def get_total_pages(cls, pdf_path: Optional[str]) -> int:
        if not pdf_path or not fitz or not os.path.exists(pdf_path):
            return 1
        try:
            doc = fitz.open(pdf_path)
            total = len(doc)
            doc.close()
            return total
        except Exception:
            return 1

    @classmethod
    def get_single_page_data(cls, pdf_path: Optional[str], page_num: int, output_dir: str) -> Dict[str, Any]:
        """
        Extracts clean body blocks, relative coordinates for interactive PDF highlighter,
        renders vector SVG with embedded bezier curves (text_as_path=True for 100% math accuracy),
        and accurately stitches incomplete sentences across page boundaries.
        """
        if not pdf_path or not fitz or not os.path.exists(pdf_path):
            return {
                "page_num": page_num,
                "total_pages": 1,
                "blocks": [],
                "paragraphs": [],
                "svg_content": "",
                "stitched_prefix": "",
                "image_path": None
            }

        os.makedirs(output_dir, exist_ok=True)
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        idx = max(0, min(page_num - 1, total_pages - 1))
        page = doc[idx]
        actual_page_num = idx + 1

        # 1. Compute Content Bounding Box to Crop Empty Margins (Ignore vertical arXiv stamp & noise)
        orig_rect = page.rect
        blocks = page.get_text("blocks")
        rects = []
        for b in blocks:
            txt = b[4].strip()
            if "arxiv:" in txt.lower():
                continue
            if (b[2] - b[0] < 35) and (b[3] - b[1] > 60):
                continue
            # Keep text if longer than 3 chars or contains math indicators/equation numbers
            if len(txt) > 3 or re.search(r'[=∑∫∇∂±≤≥∈≠≈×÷]|\(\s*\d+\s*\)', txt):
                rects.append(fitz.Rect(b[:4]))

        for d in page.get_drawings():
            if d["rect"].x0 > 35:
                rects.append(d["rect"])

        # Collect embedded raster images bounding boxes (Figures, Charts, Photos)
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    img_rects = page.get_image_rects(xref)
                    for ir in img_rects:
                        # Ignore tiny decorative icons (< 30x30 pt) or margin arXiv stamps (x0 < 35)
                        if ir.width > 30 and ir.height > 30 and ir.x0 > 20:
                            rects.append(ir)
                except Exception:
                    pass
        except Exception:
            pass

        if rects:
            union = rects[0]
            for r in rects[1:]:
                union |= r
            
            padding = 10
            crop_rect = fitz.Rect(
                max(0, union.x0 - padding),
                max(0, union.y0 - padding),
                min(orig_rect.x1, union.x1 + padding),
                min(orig_rect.y1, union.y1 + padding)
            )
            if crop_rect.width < 100 or crop_rect.height < 100:
                crop_rect = orig_rect
        else:
            crop_rect = orig_rect

        # 2. Render Flawless Vector SVG (text_as_path=True renders all math, integrals, Greek letters & formulas as vector curves)
        page.set_cropbox(crop_rect)
        raw_svg = page.get_svg_image(text_as_path=True)
        responsive_svg = re.sub(r'<svg\s+', '<svg style="width: 100%; height: auto; display: block;" ', raw_svg, count=1)
        svg_path = os.path.join(output_dir, f"page_{actual_page_num}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(responsive_svg)

        # Also save high-res PNG for fallback
        page_img_path = os.path.join(output_dir, f"page_{actual_page_num}.png")
        pix = page.get_pixmap(clip=crop_rect, dpi=180)
        pix.save(page_img_path)

        # 3. Translatable blocks. A references section opened on an earlier page keeps running.
        references_open = [False]
        for prev_index in range(idx):
            references_open.append(VisualHighlighter.references_state_after_page(doc[prev_index], references_open[-1]))
        clean_blocks, raw_paragraphs = VisualHighlighter.extract_aligned_page_blocks(
            doc_or_page=page,
            crop_rect=crop_rect,
            in_references=references_open[idx]
        )

        # The unfinished last sentence moves to the next page.
        complete_part, _ = cls._carried_fragment(clean_blocks)
        if complete_part:
            clean_blocks[-1]["text"] = complete_part
            raw_paragraphs[-1] = complete_part

        # Display formulas are shown as the original rendering (see VisualHighlighter._equation_regions).
        for number, block in enumerate([b for b in clean_blocks if b.get("kind") == "equation"], 1):
            x0, y0, x1, y1 = block["raw_rect"]
            clip = fitz.Rect(x0 - 3, y0 - 3, x1 + 3, y1 + 3) & page.rect
            image_path = os.path.join(output_dir, f"page_{actual_page_num}_formula_{number}.png")
            page.get_pixmap(clip=clip, matrix=fitz.Matrix(3, 3), alpha=False).save(image_path)
            block["image_path"] = image_path
            block["image_width_pt"] = round(clip.width, 1)

        # 4. Stitch the previous page's unfinished sentence, taken from its body text (never a table or caption)
        stitched_prefix = ""
        if idx > 0:
            prev_blocks, _ = VisualHighlighter.extract_aligned_page_blocks(doc[idx - 1], in_references=references_open[idx - 1])
            _, stitched_prefix = cls._carried_fragment(prev_blocks)

        doc.close()

        return {
            "page_num": actual_page_num,
            "total_pages": total_pages,
            "blocks": clean_blocks,
            "paragraphs": raw_paragraphs,
            "svg_content": responsive_svg,
            "svg_path": svg_path,
            "stitched_prefix": stitched_prefix,
            "image_path": page_img_path
        }

    @classmethod
    def _carried_fragment(cls, blocks):
        """(complete part, unfinished last sentence) of a page's final body paragraph, or empty strings."""
        if not blocks or blocks[-1].get("kind") != "text":
            return "", ""
        last_text = blocks[-1]["text"].strip()
        if re.search(r'[\.\?\!\:\;]$', last_text):
            return "", ""
        complete_part, trail_part = cls._split_trailing_incomplete(last_text)
        return (complete_part, trail_part) if complete_part and len(complete_part) > 20 else ("", "")

    @classmethod
    def _split_trailing_incomplete(cls, text: str) -> (str, str):
        """Splits paragraph into complete sentences and trailing incomplete sentence."""
        text = text.strip()
        if not text or re.search(r'[\.\?\!\:\;]$', text):
            return text, ""
        
        parts = re.split(r'(\. |\? |\! )', text)
        if len(parts) <= 1:
            return "", text
        
        complete = "".join(parts[:-1]).strip()
        trailing = parts[-1].strip()
        return complete, trailing
