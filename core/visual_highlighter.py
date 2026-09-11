"""
Academic Paper Visual Highlighter & Bounding Box Synchronizer
Standalone, zero-leak module for 1:1 matching, neon glow bounding boxes, and bi-directional interactive reader linking.
"""

import os
import re
import html
import base64
from typing import List, Dict, Any, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from core.math_formatter import AcademicMathFormatter


class SimpleRect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0 = float(x0)
        self.y0 = float(y0)
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.width = max(0.0, self.x1 - self.x0)
        self.height = max(0.0, self.y1 - self.y0)
    
    def __or__(self, other: Any) -> 'SimpleRect':
        return SimpleRect(
            min(self.x0, float(other.x0)),
            min(self.y0, float(other.y0)),
            max(self.x1, float(other.x1)),
            max(self.y1, float(other.y1))
        )


class VisualHighlighter:
    """
    Precision Academic PDF Visual Highlighter & Synchronizer Engine.
    Handles coordinate normalization, multi-column sorting, 1:1 translation pairing,
    and Luminous Neon Overlays.
    """

    DEFAULT_BBOX = {
        "top": "0%",
        "left": "0%",
        "width": "100%",
        "height": "0%"
    }

    # =========================================================================
    # 1. Coordinate Normalization & Block Alignment
    # =========================================================================

    @classmethod
    def create_rect(cls, x0: float, y0: float, x1: float, y1: float) -> Any:
        if fitz:
            return fitz.Rect(x0, y0, x1, y1)
        return SimpleRect(x0, y0, x1, y1)

    @classmethod
    def compute_relative_bbox(
        cls,
        rect: Any,
        crop_rect: Any,
        pad_x: float = 0.2,
        pad_y: float = 0.2
    ) -> Dict[str, str]:
        """
        Converts PDF Rect coordinates into precision percentage strings (0.0% ~ 100.0%)
        relative to the active crop canvas dimensions.
        Robustly handles both pre-cropped (0-origin) and absolute page coordinates with zero offset drift.
        """
        try:
            c_x0 = float(crop_rect.x0)
            c_y0 = float(crop_rect.y0)
            c_width = max(1.0, float(crop_rect.width))
            c_height = max(1.0, float(crop_rect.height))

            r_x0 = float(rect.x0)
            r_y0 = float(rect.y0)
            r_x1 = float(rect.x1)
            r_y1 = float(rect.y1)

            # Strict origin detection:
            # If coordinates exceed crop canvas dimensions, they are in absolute page space -> subtract crop origin.
            # If coordinates are bounded within crop canvas dimensions, they are already relative (0-origin).
            if (r_x1 > c_width + 15.0 or r_y1 > c_height + 15.0) and (c_x0 > 0.0 or c_y0 > 0.0):
                rel_x0 = r_x0 - c_x0
                rel_y0 = r_y0 - c_y0
                rel_x1 = r_x1 - c_x0
                rel_y1 = r_y1 - c_y0
            else:
                rel_x0 = r_x0
                rel_y0 = r_y0
                rel_x1 = r_x1
                rel_y1 = r_y1

            # Clamp coordinates to crop box boundaries (0.0% ~ 100.0%)
            left_pct = max(0.0, min(100.0, (rel_x0 / c_width) * 100.0 - pad_x))
            top_pct = max(0.0, min(100.0, (rel_y0 / c_height) * 100.0 - pad_y))
            right_pct = max(0.0, min(100.0, (rel_x1 / c_width) * 100.0 + pad_x))
            bottom_pct = max(0.0, min(100.0, (rel_y1 / c_height) * 100.0 + pad_y))

            width_pct = max(1.0, min(100.0 - left_pct, right_pct - left_pct))
            height_pct = max(1.0, min(100.0 - top_pct, bottom_pct - top_pct))

            return {
                "top": f"{top_pct:.2f}%",
                "left": f"{left_pct:.2f}%",
                "width": f"{width_pct:.2f}%",
                "height": f"{height_pct:.2f}%"
            }
        except Exception:
            return cls.DEFAULT_BBOX.copy()

    @classmethod
    def sort_blocks_by_reading_flow(
        cls,
        raw_blocks: List[Any],
        page_width: float
    ) -> List[Any]:
        """
        Sorts academic blocks considering 2-column or 1-column layout flow:
        - Full-width headers (spanning > 60% of page) stay at the top.
        - Left column top-to-bottom first, then right column top-to-bottom.
        """
        if not raw_blocks:
            return []

        mid_x = page_width / 2.0
        
        left_blocks = []
        right_blocks = []
        full_blocks = []

        for b in raw_blocks:
            try:
                x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
                w = x1 - x0
                if w > page_width * 0.60:
                    full_blocks.append((y0, b))
                elif x1 < mid_x + (page_width * 0.08):
                    left_blocks.append((y0, b))
                else:
                    right_blocks.append((y0, b))
            except Exception:
                full_blocks.append((0.0, b))

        left_blocks.sort(key=lambda item: item[0])
        right_blocks.sort(key=lambda item: item[0])
        full_blocks.sort(key=lambda item: item[0])

        if len(left_blocks) >= 2 and len(right_blocks) >= 2:
            sorted_all = []
            first_col_y = min(left_blocks[0][0], right_blocks[0][0])
            for y0, b in full_blocks:
                if y0 < first_col_y:
                    sorted_all.append(b)

            sorted_all.extend([b for _, b in left_blocks])
            sorted_all.extend([b for _, b in right_blocks])

            for y0, b in full_blocks:
                if y0 >= first_col_y and b not in sorted_all:
                    sorted_all.append(b)

            return sorted_all

        return sorted(raw_blocks, key=lambda b: (b[1], b[0]))

    @classmethod
    def is_noise_or_meta(cls, text: str) -> bool:
        """
        Detects and filters out non-body academic metadata:
        - Author lists, equal contribution notices, affiliations
        - arXiv headers, conference copyright notices
        - Demo/project links, repository URLs
        - Standalone section title labels (e.g. 'Abstract')
        """
        t_clean = text.strip()
        t_low = t_clean.lower()
        
        # 1. Standalone section markers
        if re.match(r'^abstract\s*$', t_low):
            return True
        if re.match(r'^(demo page|project page|code:|website:)', t_low):
            return True

        # 2. Academic contribution / author metadata notes
        if re.search(r'equal contribution|alphabetical by given name|corresponding author|\*equal contribution|all authors contributed', t_low):
            return True

        # 3. Common paper stamps
        if re.match(r'^(arxiv:\d+|page \d+|under review|preprint\.|permission to make|copyright|published as a conference paper|proceedings of the|accepted to)', t_low):
            return True
            
        # 4. Email addresses
        if re.search(r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b', text) and len(text.split()) < 35:
            return True
            
        # 5. Corporate lab / foundry / institute affiliations
        if re.search(r'\b(lab|labs|university|department|institute|foundry)\b|\balibaba\b|\btoken foundry\b|\bgoogle research\b|\bmicrosoft\b|\btsinghua\b|\bcarnegie mellon\b|\bstanford\b|\bmit\b|\bmeta ai\b|\bopenai\b|\bdeepmind\b|\banthropic\b|\bhuggingface\b', t_low) and len(text.split()) < 30:
            return True

        # 6. URLs and repository links
        if re.search(r'https?://', t_low) or 'github.com' in t_low:
            if len(text.split()) < 25:
                return True
            
        # 7. Comma-separated Author name list detection (e.g. 'Zhihao Du, Changfeng Gao, Yuxuan Wang...', 'Bajian Xiang, Cheng Wen...')
        # Must NOT match mathematical formulas (containing =, +, ^, or equation numbers)
        if '=' in text or '+' in text or '\\' in text or '^' in text or re.search(r'\(\s*\d+\s*\)\s*$', t_clean):
            return False

        # Guard: If text contains academic research subject pronouns/nouns, it is NOT an author list
        has_paper_subject = bool(re.search(r'\b(we|our|this|paper|report|study|model|system|method|architecture|framework|network|approach|algorithm)\b', t_low))
        if not has_paper_subject:
            words = text.split()
            if text.count(',') >= 3 and len(words) < 50:
                verb_count = len(re.findall(r'\b(is|are|was|were|presents?|proposed?|proposes?|shows?|achieves?|provides?|combines?|introduces?|evaluates?|demonstrates?|develops?|consists?)\b', t_low))
                if verb_count == 0:
                    return True

        return False

    @classmethod
    def extract_aligned_page_blocks(
        cls,
        doc_or_page: Any,
        page_idx: int = 0,
        crop_rect: Any = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extracts clean body paragraphs, separates paper title & abstract,
        merges multi-line fragmented abstract/body blocks into continuous paragraphs,
        and computes ground-truth bounding boxes relative to crop_rect.
        """
        if doc_or_page is None:
            return [], []

        page = doc_or_page if not hasattr(doc_or_page, "open") else doc_or_page[page_idx]
        actual_crop = crop_rect if crop_rect is not None else page.rect

        raw_blocks = page.get_text("blocks")
        sorted_blocks = cls.sort_blocks_by_reading_flow(raw_blocks, page.rect.width)

        candidate_items = []
        is_in_abstract = False

        for b in sorted_blocks:
            try:
                text = b[4].strip()
            except Exception:
                continue

            # Check length: allow short blocks if they contain mathematical operators or equation numbers
            has_math_in_raw = bool(re.search(r'[=∑∫∏∇∂±×÷≈≠≤≥∈∉⊂⊆∪∩→←⇒↔∞√]|\b(?:alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|tau|phi|psi|omega)\b|\\|\^|_|\(\s*\d+\s*\)', text, flags=re.IGNORECASE))
            if len(text) < 5 and not has_math_in_raw:
                continue

            # Check if this is the next major section header (e.g. 1 Introduction) -> ends abstract
            if re.match(r'^(1|i|i\.)\s+(introduction|overview|background)\b', text, flags=re.IGNORECASE):
                is_in_abstract = False

            # Check if this is the standalone Abstract heading
            if re.match(r'^abstract\s*$', text, flags=re.IGNORECASE):
                is_in_abstract = True
                continue

            if cls.is_noise_or_meta(text) or cls.is_figure_table_caption_or_chart(text):
                continue
            
            clean_p = cls.clean_academic_text(text)
            
            # Guard mathematical formulas and numbered equations from being dropped by the length filter
            has_math_indicators = bool(re.search(r'[=∑∫∏∇∂±×÷≈≠≤≥∈∉⊂⊆∪∩→←⇒↔∞√]|\\\\|\\^|_\{|\$|\b(?:alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|tau|phi|psi|omega)\b', clean_p, flags=re.IGNORECASE))
            has_equation_number = bool(re.search(r'\(\s*\d+\s*\)\s*$', clean_p))
            
            if len(clean_p) < 15 and not has_math_indicators and not has_equation_number:
                continue

            had_abstract_prefix = bool(re.match(r'^abstract\s*[:\.\-]?\s*', clean_p, flags=re.IGNORECASE))
            if had_abstract_prefix:
                clean_p = re.sub(r'^abstract\s*[:\.\-]?\s*', '', clean_p, flags=re.IGNORECASE).strip()
                is_in_abstract = True
                if not clean_p:
                    continue

            rect = cls.create_rect(b[0], b[1], b[2], b[3])

            candidate_items.append({
                "text": clean_p,
                "rect": rect,
                "is_abstract": is_in_abstract
            })

        # 2. Semantic Paragraph Stitcher: Merge fragmented blocks that belong to the same paragraph
        merged_items = []
        for item in candidate_items:
            if not merged_items:
                merged_items.append(item)
                continue

            prev = merged_items[-1]
            prev_text = prev["text"].strip()
            curr_text = item["text"].strip()

            both_abstract = bool(prev.get("is_abstract") and item.get("is_abstract"))
            prev_ends_sentence = bool(re.search(r'[\.\?\!\:\;]$', prev_text))
            curr_starts_lower = curr_text[0].islower() if curr_text else False
            
            # Isolated numbered equations or standalone formulas should stay distinct
            prev_is_numbered_eq = bool(re.search(r'\(\s*\d+\s*\)\s*$', prev_text))
            curr_is_numbered_eq = bool(re.search(r'\(\s*\d+\s*\)\s*$', curr_text)) or ('=' in curr_text and len(curr_text.split()) < 10)
            
            # Math formula guards
            prev_is_short_math = bool(re.search(r'[=∑∫∏∇∂±×÷≈≠≤≥∈∉⊂⊆∪∩→←⇒↔∞√]|\\\\|\\^|_\{|\$', prev_text) and len(prev_text.split()) < 15)
            curr_is_short_math = bool(re.search(r'[=∑∫∏∇∂±×÷≈≠≤≥∈∉⊂⊆∪∩→←⇒↔∞√]|\\\\|\\^|_\{|\$', curr_text) and len(curr_text.split()) < 15)
            
            # Figure/Table caption guards
            prev_is_caption = bool(re.match(r'^(figure|fig\.|table|tab\.)\s*\d+', prev_text, flags=re.IGNORECASE))
            curr_is_caption = bool(re.match(r'^(figure|fig\.|table|tab\.)\s*\d+', curr_text, flags=re.IGNORECASE))

            # Check vertical proximity & same column alignment
            y_gap = item["rect"].y0 - prev["rect"].y1
            x_diff = abs(item["rect"].x0 - prev["rect"].x0)
            is_same_column = (x_diff < 40.0) or (item["rect"].x0 < prev["rect"].x1 and item["rect"].x1 > prev["rect"].x0)

            should_merge = False
            if is_same_column and (-5.0 <= y_gap < 35.0):
                if both_abstract and y_gap < 60.0:
                    should_merge = True
                elif not prev_ends_sentence or curr_starts_lower:
                    should_merge = True

            if prev_is_numbered_eq or curr_is_numbered_eq or prev_is_short_math or curr_is_short_math or prev_is_caption or curr_is_caption:
                should_merge = False

            if should_merge:
                prev["text"] = f"{prev_text} {curr_text}"
                prev["rect"] = prev["rect"] | item["rect"]  # Union bounding box
                if item.get("is_abstract"):
                    prev["is_abstract"] = True
            else:
                merged_items.append(item)

        clean_blocks = []
        raw_paragraphs = []

        for item in merged_items:
            rect = item["rect"]
            bbox = cls.compute_relative_bbox(rect, actual_crop)
            clean_text = item["text"]

            clean_blocks.append({
                "text": clean_text,
                "bbox": bbox,
                "raw_rect": [rect.x0, rect.y0, rect.x1, rect.y1]
            })
            raw_paragraphs.append(clean_text)

        return clean_blocks, raw_paragraphs

    # =========================================================================
    # 2. Text Normalization & Academic Noise Filtering
    # =========================================================================

    @classmethod
    def clean_academic_text(cls, text: str) -> str:
        """Removes hyphenation at line breaks and merges wrapped lines."""
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        text = re.sub(r'(?<!\n)\n(?!\n|[A-Z0-9\.\#\*\-])', ' ', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    @classmethod
    def is_figure_table_caption_or_chart(cls, text: str) -> bool:
        """
        Filters isolated chart numeric columns, subfigure label fragments, 
        chart legend labels, and empty caption headers, while preserving informative Figure/Table captions.
        """
        t_low = text.lower().strip()
        words = text.split()

        # 1. Subfigure (a), (b), (c) standalone label fragments
        if re.match(r'^\(?[a-f]\)\s*$', t_low) or re.match(r'^\(?[a-f]\)\s+[a-z0-9_\-\s]{1,15}$', t_low):
            return True

        # 2. Chart/Table pure numeric data series (e.g. "82.4 19.3 0.94 12.5")
        if len(words) < 25:
            num_count = sum(1 for w in words if re.match(r'^\d+(\.\d+)?%?$', w))
            if len(words) > 0 and (num_count / len(words) > 0.50):
                return True

        # 3. Empty or trivial caption fragments without actual descriptive text (e.g. just "Figure 1." or "Table 2")
        if re.match(r'^(figure|fig\.|fig|table|tab\.|tab)\s*(\d+|[a-z])[\.:]?\s*$', t_low):
            return True

        # 4. Multi-label benchmark chart/figure legends (e.g. 'CV3-Eval: fr\nCV3-Eval: it SEED: hard MaskGCT...')
        # Dense occurrence of labels/eval keywords without continuous sentence structure
        chart_tags = len(re.findall(r'\b(eval|eval:|seed:|wer:|cer:|eer:|mos:|sim:|sim-o|sim-r|f5-tts|maskgct|cosyvoice|valle|audiogpt)\b', t_low))
        if chart_tags >= 2 and not re.search(r'[\.\?\!]$', text.strip()) and len(words) < 40:
            return True
        if text.count(':') >= 3 and len(words) < 30 and not re.search(r'[\.\?\!]$', text.strip()):
            return True

        return False

    # =========================================================================
    # 3. 1:1 Translation Pair Alignment & Safety Guard
    # =========================================================================

    @classmethod
    def align_translation_pairs(
        cls,
        extracted_texts: List[str],
        translated_texts: List[str],
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Guarantees 1:1 pairing between original English paragraphs and Korean translations
        with valid bounding box metadata. Never drops a block or misaligns IDs.
        """
        pairs = []
        total_items = max(len(extracted_texts), len(translated_texts))
        
        for idx in range(total_items):
            p_id = idx + 1
            en_text = extracted_texts[idx] if idx < len(extracted_texts) else ""
            ko_text = translated_texts[idx] if idx < len(translated_texts) else en_text
            
            # Extract bbox from block metadata if available
            bbox = cls.DEFAULT_BBOX.copy()
            if blocks and idx < len(blocks):
                block_bbox = blocks[idx].get("bbox")
                if isinstance(block_bbox, dict) and "top" in block_bbox and "left" in block_bbox:
                    bbox = block_bbox

            pairs.append({
                "id": p_id,
                "en": en_text,
                "ko": ko_text,
                "bbox": bbox
            })

        return pairs

    # =========================================================================
    # 4. Visual Rendering Engines (HTML & SVG Overlays)
    # =========================================================================

    @classmethod
    def generate_single_overlay_html(
        cls,
        pair_id: int,
        bbox: Dict[str, str],
        title_hint: str = ""
    ) -> str:
        """
        Renders a single precision bounding box with Luminous Neon Glow, animated pulse,
        and self-contained direct DOM hover/click listeners.
        """
        top = bbox.get("top", "0%")
        left = bbox.get("left", "0%")
        w = bbox.get("width", "0%")
        h = bbox.get("height", "0%")
        safe_hint = html.escape(title_hint or f"원문 단락 [{pair_id}]")

        enter_code = f"var p=document.getElementById('para-item-{pair_id}');if(p)p.classList.add('active');this.classList.add('active');this.style.opacity='1';if(window._agPairHover)window._agPairHover({pair_id},true,'hl');"
        leave_code = f"var p=document.getElementById('para-item-{pair_id}');if(p&&!p.classList.contains('pinned'))p.classList.remove('active');if(!this.classList.contains('pinned')){{this.classList.remove('active');this.style.opacity='';}}if(window._agPairHover)window._agPairHover({pair_id},false,'hl');"
        click_code = f"if(window._agPairClick){{window._agPairClick({pair_id},'hl');}}else{{var isP=this.classList.toggle('pinned');this.style.opacity=isP?'1':'';var p=document.getElementById('para-item-{pair_id}');if(p)p.classList.toggle('pinned',isP);}}"

        return (
            f'<div id="pdf-hl-{pair_id}" data-id="{pair_id}" class="pdf-highlight-overlay" '
            f'style="top:{top}; left:{left}; width:{w}; height:{h};" '
            f'onmouseenter="{enter_code}" '
            f'onmouseover="{enter_code}" '
            f'onmouseleave="{leave_code}" '
            f'onmouseout="{leave_code}" '
            f'onclick="{click_code}" '
            f'title="{safe_hint}">'
            f'<span class="pdf-hl-badge">[{pair_id}]</span>'
            f'</div>'
        )

    @classmethod
    def render_overlay_canvas(
        cls,
        pairs: List[Dict[str, Any]],
        current_page: int,
        svg_content: str = "",
        image_path: Optional[str] = None
    ) -> str:
        """
        Builds the complete Left-side Native Vector SVG / High-Res Image PDF Viewport
        with embedded Luminous Neon Overlays.
        """
        overlays_html = "".join([
            cls.generate_single_overlay_html(
                pair_id=p.get("id", idx + 1),
                bbox=p.get("bbox") or cls.DEFAULT_BBOX
            )
            for idx, p in enumerate(pairs)
        ])

        content_body = ""
        if svg_content:
            content_body = f'<div class="pdf-svg-container">{svg_content}</div>'
        elif image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
            content_body = f'<img src="data:image/png;base64,{b64_img}" style="width:100%; display:block;" />'
        else:
            content_body = '<div style="padding: 2rem; color: #86868B;">페이지 원문을 불러올 수 없습니다.</div>'

        canvas_html = f'''
        <div class="unified-reader-frame" key="pdf-frame-{current_page}">
            <div class="pdf-viewer-wrapper" id="pdf-scroll-pane-{current_page}">
                <div class="pdf-content-canvas">
                    {content_body}
                    {overlays_html}
                </div>
            </div>
        </div>
        '''
        return "".join([line.strip() for line in canvas_html.splitlines()])

    @classmethod
    def render_translation_paragraphs(
        cls,
        pairs: List[Dict[str, Any]],
        current_page: int,
        font_size: int = 16,
        line_height: float = 1.85
    ) -> str:
        """
        Builds the Right-side Scrollable Korean Translation Viewport with Math Formatting
        and self-contained direct DOM interactive handlers.
        """
        if not pairs:
            return (
                f'<div class="unified-reader-frame" key="trans-frame-{current_page}">'
                f'<div class="scrollable-trans-box" id="trans-scroll-pane-{current_page}">'
                f'<div style="color: #86868B; padding: 1.5rem;">이 페이지에는 텍스트 본문이 없습니다 (도표 또는 수식 전용).</div>'
                f'</div></div>'
            )

        paras_html = []
        for pair in pairs:
            p_id = pair.get("id", 1)
            ko_raw = pair.get("ko", "").strip()

            try:
                if hasattr(AcademicMathFormatter, "format_math_in_text"):
                    ko_formatted = AcademicMathFormatter.format_math_in_text(ko_raw)
                else:
                    ko_formatted = ko_raw

                if hasattr(AcademicMathFormatter, "escape_html_outside_math"):
                    ko_clean = AcademicMathFormatter.escape_html_outside_math(ko_formatted)
                else:
                    ko_clean = html.escape(ko_formatted).replace("&amp;", "&")
            except Exception:
                ko_clean = html.escape(ko_raw)

            enter_para = f"var h=document.getElementById('pdf-hl-{p_id}');if(h){{h.classList.add('active');h.style.opacity='1';}}this.classList.add('active');if(window._agPairHover)window._agPairHover({p_id},true,'para');"
            leave_para = f"var h=document.getElementById('pdf-hl-{p_id}');if(h&&!h.classList.contains('pinned')){{h.classList.remove('active');h.style.opacity='';}}if(!this.classList.contains('pinned'))this.classList.remove('active');if(window._agPairHover)window._agPairHover({p_id},false,'para');"
            click_para = f"if(window._agPairClick){{window._agPairClick({p_id},'para');}}else{{var isP=this.classList.toggle('pinned');var h=document.getElementById('pdf-hl-{p_id}');if(h){{h.classList.toggle('pinned',isP);h.style.opacity=isP?'1':'';}}}}"

            para_style = f"font-size: {font_size}px; line-height: {line_height};"
            para_tag = (
                f'<div class="doc-para" style="{para_style}" id="para-item-{p_id}" data-id="{p_id}" '
                f'onmouseenter="{enter_para}" '
                f'onmouseover="{enter_para}" '
                f'onmouseleave="{leave_para}" '
                f'onmouseout="{leave_para}" '
                f'onclick="{click_para}">'
                f'<span class="doc-para-idx">[{p_id}]</span>{ko_clean}</div>'
            )
            paras_html.append(para_tag)

        scrollable_html = (
            f'<div class="unified-reader-frame" key="trans-frame-{current_page}">'
            f'<div class="scrollable-trans-box" id="trans-scroll-pane-{current_page}">'
            f'{"".join(paras_html)}'
            f'</div></div>'
        )
        return scrollable_html

    # =========================================================================
    # 5. Encapsulated Standalone CSS & JS Controller Assets
    # =========================================================================

    @classmethod
    def get_neon_css(cls) -> str:
        """
        Returns the self-contained Moonlight Luminous Neon Glow & Box Border CSS.
        Guarantees flawless styling even if external styles.py is missing or overridden.
        """
        return """
<style id="ag-visual-highlighter-styles">
    /* 🟡 PDF Viewport Canvas & Moonlight Neon Highlighter Overlays */
    .pdf-viewer-wrapper {
        position: relative !important;
        width: 100% !important;
        height: 100% !important;
        overflow-y: auto !important;
        background: #FFFFFF !important;
        box-sizing: border-box !important;
        scroll-behavior: smooth !important;
    }

    .pdf-content-canvas {
        position: relative !important;
        width: 100% !important;
        display: block !important;
    }

    .pdf-svg-container {
        width: 100% !important;
        display: block !important;
        user-select: text !important;
        -webkit-user-select: text !important;
    }

    .pdf-svg-container svg {
        width: 100% !important;
        height: auto !important;
        display: block !important;
    }

    .pdf-highlight-overlay {
        position: absolute !important;
        pointer-events: auto !important;
        border-radius: 6px !important;
        margin: 0 !important;
        padding: 0 !important;
        transition: opacity 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease !important;
        opacity: 0 !important;
        background-color: rgba(254, 240, 138, 0.15) !important;
        border: 1.5px solid transparent !important;
        box-shadow: none !important;
        z-index: 50 !important;
        cursor: pointer !important;
        box-sizing: border-box !important;
    }

    /* Active / Hover Moonlight Neon Glow */
    .pdf-highlight-overlay:hover, 
    .pdf-highlight-overlay.active {
        opacity: 1 !important;
        background-color: rgba(254, 240, 138, 0.42) !important;
        border: 2px solid #F59E0B !important;
        box-shadow: 
            0 0 0 2px rgba(245, 158, 11, 0.45),
            0 4px 20px rgba(245, 158, 11, 0.32),
            inset 0 0 14px rgba(254, 240, 138, 0.35) !important;
        z-index: 65 !important;
        animation: luminous-glow-pulse 2.2s infinite ease-in-out !important;
    }

    /* Pinned Neon State */
    .pdf-highlight-overlay.pinned {
        opacity: 1 !important;
        background-color: rgba(254, 240, 138, 0.52) !important;
        border: 2.5px solid #D97706 !important;
        box-shadow: 
            0 0 0 3px rgba(217, 119, 6, 0.55),
            0 6px 26px rgba(217, 119, 6, 0.45),
            inset 0 0 18px rgba(254, 240, 138, 0.45) !important;
        z-index: 75 !important;
    }

    /* Numeric ID Badge on Box */
    .pdf-hl-badge {
        position: absolute !important;
        top: -11px !important;
        left: 6px !important;
        background: #F59E0B !important;
        color: #FFFFFF !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        padding: 1px 7px !important;
        border-radius: 9999px !important;
        box-shadow: 0 2px 8px rgba(245, 158, 11, 0.5) !important;
        pointer-events: none !important;
        opacity: 0 !important;
        transition: opacity 0.15s ease !important;
        line-height: 1.2 !important;
    }

    .pdf-highlight-overlay:hover .pdf-hl-badge, 
    .pdf-highlight-overlay.active .pdf-hl-badge, 
    .pdf-highlight-overlay.pinned .pdf-hl-badge {
        opacity: 1 !important;
    }

    /* Luminous Neon Pulse Keyframe */
    @keyframes luminous-glow-pulse {
        0%, 100% {
            box-shadow: 0 0 0 1.5px rgba(245, 158, 11, 0.40), 0 3px 14px rgba(245, 158, 11, 0.22), inset 0 0 10px rgba(254, 240, 138, 0.25);
        }
        50% {
            box-shadow: 0 0 0 2.5px rgba(245, 158, 11, 0.70), 0 5px 24px rgba(245, 158, 11, 0.40), inset 0 0 16px rgba(254, 240, 138, 0.40);
        }
    }

    /* 🔵 Translation Paragraph (Apple Blue Highlight on Hover / Pin) */
    .scrollable-trans-box {
        position: relative !important;
        height: 100% !important;
        overflow-y: auto !important;
        padding: 1.6rem 1.8rem !important;
        box-sizing: border-box !important;
        scroll-behavior: smooth !important;
    }

    .doc-para {
        margin-bottom: 1.15rem !important;
        padding: 0.85rem 1.1rem !important;
        border-radius: 12px !important;
        border-left: 4px solid transparent !important;
        background-color: transparent !important;
        transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1) !important;
        cursor: pointer !important;
    }

    .doc-para:hover, .doc-para.active {
        background-color: #E8F2FF !important;
        border-left: 4px solid #0071E3 !important;
        box-shadow: 0 4px 16px rgba(0, 113, 227, 0.12) !important;
        color: #1D1D1F !important;
    }

    .doc-para.pinned {
        background-color: #D2E5FF !important;
        border-left: 5px solid #0056B3 !important;
        box-shadow: 0 4px 20px rgba(0, 113, 227, 0.25) !important;
        color: #1D1D1F !important;
    }

    .doc-para-idx {
        font-weight: 800 !important;
        color: #0071E3 !important;
        font-size: 0.84rem !important;
        margin-right: 0.5rem !important;
        user-select: none !important;
    }
</style>
"""

    @classmethod
    def get_highlighter_js(cls) -> str:
        """
        Returns the self-contained JavaScript Synchronizer Engine.
        Handles hover pairing, click pin toggle, re-click unpin, background dismiss, and auto smooth-scrolling.
        Equipped with Document-Level Event Delegation for 100% reliability across Streamlit reruns.
        """
        return """
(function() {
    var win = (typeof window !== 'undefined') ? window : this;
    var doc = (typeof document !== 'undefined') ? document : (win.document || {});

    // Helper: Precision relative scroll calculator (immune to scale, padding, and zoom)
    function scrollToTarget(elem, container) {
        if (!elem || !container) return;
        try {
            var elemRect = elem.getBoundingClientRect();
            var contRect = container.getBoundingClientRect();
            var relativeTop = elemRect.top - contRect.top;
            var targetScroll = container.scrollTop + relativeTop - (container.clientHeight / 3);
            container.scrollTo({ top: Math.max(0, targetScroll), behavior: 'smooth' });
        } catch(err) {
            try {
                elem.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } catch(e) {}
        }
    }

    win._agPinnedId = win._agPinnedId || null;
    win._agCurrentPinnedId = win._agCurrentPinnedId || null;

    // 1. Global Synchronized Highlighter Core Function
    var pairHover = function(id, active, source) {
        var numId = parseInt(id, 10);
        if (!numId) return;

        try {
            var hl = doc.getElementById('pdf-hl-' + numId);
            var para = doc.getElementById('para-item-' + numId);

            if (active) {
                if (hl) {
                    hl.classList.add('active');
                    hl.style.opacity = '1';
                }
                if (para) {
                    para.classList.add('active');
                }
                if (!win._agPinnedId && !win._agCurrentPinnedId) {
                    if (source === 'para' && hl) {
                        var pdfPane = hl.closest('.pdf-viewer-wrapper') || doc.querySelector('.pdf-viewer-wrapper');
                        if (pdfPane) scrollToTarget(hl, pdfPane);
                    } else if (source === 'hl' && para) {
                        var transPane = para.closest('.scrollable-trans-box') || doc.querySelector('.scrollable-trans-box');
                        if (transPane) scrollToTarget(para, transPane);
                    }
                }
            } else {
                if (hl && !hl.classList.contains('pinned')) {
                    hl.classList.remove('active');
                    hl.style.opacity = '';
                }
                if (para && !para.classList.contains('pinned')) {
                    para.classList.remove('active');
                }
            }
        } catch(e) {
            console.error('[Anti-Paper Hover Error]', e);
        }
    };

    var pairClick = function(id, source) {
        var numId = parseInt(id, 10);
        if (!numId) return;

        try {
            var hl = doc.getElementById('pdf-hl-' + numId);
            var para = doc.getElementById('para-item-' + numId);
            var isCurrentlyPinned = (win._agPinnedId === numId) || (win._agCurrentPinnedId === numId) ||
                                    (para && para.classList.contains('pinned')) || 
                                    (hl && hl.classList.contains('pinned'));

            var allPinned = doc.querySelectorAll('.doc-para.pinned, .pdf-highlight-overlay.pinned');
            allPinned.forEach(function(el) { 
                el.classList.remove('pinned'); 
                if (el.classList.contains('pdf-highlight-overlay') && !el.classList.contains('active')) {
                    el.style.opacity = '';
                }
            });

            if (isCurrentlyPinned) {
                win._agPinnedId = null;
                win._agCurrentPinnedId = null;
                if (para) para.classList.add('active');
                if (hl) {
                    hl.classList.add('active');
                    hl.style.opacity = '1';
                }
            } else {
                win._agPinnedId = numId;
                win._agCurrentPinnedId = numId;
                var allActive = doc.querySelectorAll('.doc-para.active, .pdf-highlight-overlay.active');
                allActive.forEach(function(el) {
                    if (el.id !== ('para-item-' + numId) && el.id !== ('pdf-hl-' + numId)) {
                        el.classList.remove('active');
                        if (el.classList.contains('pdf-highlight-overlay')) el.style.opacity = '';
                    }
                });

                if (para) para.classList.add('pinned', 'active');
                if (hl) {
                    hl.classList.add('pinned', 'active');
                    hl.style.opacity = '1';
                }

                if (source === 'para' && hl) {
                    var pdfPane = hl.closest('.pdf-viewer-wrapper') || doc.querySelector('.pdf-viewer-wrapper');
                    if (pdfPane) scrollToTarget(hl, pdfPane);
                } else if (source === 'hl' && para) {
                    var transPane = para.closest('.scrollable-trans-box') || doc.querySelector('.scrollable-trans-box');
                    if (transPane) scrollToTarget(para, transPane);
                }
            }
        } catch(e) {
            console.error('[Anti-Paper Click Error]', e);
        }
    };

    win._agPairHover = pairHover;
    win._agPairClick = pairClick;
    win._agActivatePair = pairHover;
    win._agTogglePinPair = pairClick;
    try {
        if (win.parent && win.parent !== win) {
            win.parent._agPairHover = pairHover;
            win.parent._agPairClick = pairClick;
            win.parent._agActivatePair = pairHover;
            win.parent._agTogglePinPair = pairClick;
        }
    } catch(e) {}

    // 2. Document-Level Event Delegation for 100% Robustness
    if (!win._agHighlighterDelegationInstalled) {
        win._agHighlighterDelegationInstalled = true;

        doc.addEventListener('mouseover', function(e) {
            var paraTarget = e.target.closest('.doc-para');
            if (paraTarget) {
                var pId = paraTarget.getAttribute('data-id');
                if (pId) pairHover(pId, true, 'para');
                return;
            }
            var hlTarget = e.target.closest('.pdf-highlight-overlay');
            if (hlTarget) {
                var hId = hlTarget.getAttribute('data-id');
                if (hId) pairHover(hId, true, 'hl');
                return;
            }
        }, true);

        doc.addEventListener('mouseout', function(e) {
            var paraTarget = e.target.closest('.doc-para');
            if (paraTarget) {
                var pId = paraTarget.getAttribute('data-id');
                if (pId && (!e.relatedTarget || !e.relatedTarget.closest('#para-item-' + pId))) {
                    pairHover(pId, false, 'para');
                }
                return;
            }
            var hlTarget = e.target.closest('.pdf-highlight-overlay');
            if (hlTarget) {
                var hId = hlTarget.getAttribute('data-id');
                if (hId && (!e.relatedTarget || !e.relatedTarget.closest('#pdf-hl-' + hId))) {
                    pairHover(hId, false, 'hl');
                }
                return;
            }
        }, true);

        doc.addEventListener('click', function(e) {
            var paraTarget = e.target.closest('.doc-para');
            if (paraTarget) {
                var pId = paraTarget.getAttribute('data-id');
                if (pId) pairClick(pId, 'para');
                return;
            }
            var hlTarget = e.target.closest('.pdf-highlight-overlay');
            if (hlTarget) {
                var hId = hlTarget.getAttribute('data-id');
                if (hId) pairClick(hId, 'hl');
                return;
            }
            // Outside click -> deselect all pinned
            if (!paraTarget && !hlTarget) {
                if (win._agPinnedId !== null || win._agCurrentPinnedId !== null) {
                    win._agPinnedId = null;
                    win._agCurrentPinnedId = null;
                    var allPinned = doc.querySelectorAll('.doc-para.pinned, .pdf-highlight-overlay.pinned, .doc-para.active, .pdf-highlight-overlay.active');
                    allPinned.forEach(function(el) {
                        el.classList.remove('pinned', 'active');
                        if (el.classList.contains('pdf-highlight-overlay')) el.style.opacity = '';
                    });
                }
            }
        }, true);
    }
})();
"""

    @classmethod
    def get_controller_assets(cls) -> str:
        """
        Returns combined self-contained CSS + Native JS script trigger markup.
        Can be injected into any Streamlit view with zero external dependencies.
        """
        css = cls.get_neon_css()
        js = cls.get_highlighter_js()
        b64_js = base64.b64encode(js.encode("utf-8")).decode("ascii")
        injector = f'''
        <svg width="0" height="0" style="display:none;" onload="
            if(!window._agControllerInstalled){{
                window._agControllerInstalled = true;
                try {{
                    var s = document.createElement('script');
                    s.textContent = decodeURIComponent(escape(atob('{b64_js}')));
                    document.head.appendChild(s);
                }} catch(e) {{
                    console.error('[Anti-Paper] Controller mount error:', e);
                }}
            }}
        "></svg>
        <script>{js}</script>
        '''
        return f"{css}\n{injector}"
