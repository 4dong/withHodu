"""
Visual Materials Extractor for Academic Papers
Extracts embedded images, figures, charts, and renders high-res page snapshots for tables and visual verification.
"""

import os
import re
from typing import List, Dict, Any, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

class PaperVisualExtractor:
    """Extracts figures, tables, and visual screenshots from PDF documents."""

    @classmethod
    def extract_visuals(cls, pdf_path: str, output_dir: str, max_pages: int = 20) -> Dict[str, Any]:
        """Extracts images and page screenshots from a PDF file."""
        if not fitz or not os.path.exists(pdf_path):
            return {"figures": [], "page_screenshots": [], "total_visuals": 0}

        figures_dir = os.path.join(output_dir, "visuals")
        os.makedirs(figures_dir, exist_ok=True)

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_to_process = min(total_pages, max_pages)

        extracted_figures = []
        page_screenshots = []
        seen_hashes = set()

        for page_idx in range(pages_to_process):
            page = doc[page_idx]
            page_num = page_idx + 1
            page_text = page.get_text()

            # Detect figure and table captions on this page
            captions = cls._find_captions_in_text(page_text)

            # 1. Render High-Resolution Page Screenshot (150 DPI)
            pix = page.get_pixmap(dpi=150)
            page_img_path = os.path.join(figures_dir, f"page_{page_num}.png")
            pix.save(page_img_path)

            has_visuals_on_page = len(captions) > 0

            page_screenshots.append({
                "page_num": page_num,
                "image_path": page_img_path,
                "has_captions": has_visuals_on_page,
                "captions": captions
            })

            # 2. Extract Embedded Raster Images
            image_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                width = base_image["width"]
                height = base_image["height"]

                # Filter out tiny logos, bullets, or icons (< 120x120 px)
                if width < 120 or height < 120:
                    continue

                # Filter duplicates by byte length
                img_hash = len(image_bytes)
                if img_hash in seen_hashes:
                    continue
                seen_hashes.add(img_hash)

                fig_filename = f"fig_p{page_num}_{img_idx + 1}.{image_ext}"
                fig_path = os.path.join(figures_dir, fig_filename)
                with open(fig_path, "wb") as f:
                    f.write(image_bytes)

                # Match caption if available
                matched_caption = captions[0] if captions else f"Figure on Page {page_num}"

                extracted_figures.append({
                    "id": f"fig_{page_num}_{img_idx}",
                    "page_num": page_num,
                    "file_path": fig_path,
                    "width": width,
                    "height": height,
                    "caption": matched_caption
                })

        doc.close()

        return {
            "figures": extracted_figures,
            "page_screenshots": page_screenshots,
            "total_visuals": len(extracted_figures)
        }

    @classmethod
    def _find_captions_in_text(cls, text: str) -> List[str]:
        """Detects Figure, Fig., Table captions in page text."""
        captions = []
        # Regex to capture Figure 1: ... or Table 2: ... or Fig. 1 ...
        pattern = r'((?:Figure|Fig\.|Table)\s+\d+[\.:\s][^\n\r]{10,160})'
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            clean_m = m.replace('\n', ' ').strip()
            if clean_m not in captions:
                captions.append(clean_m)
        return captions
