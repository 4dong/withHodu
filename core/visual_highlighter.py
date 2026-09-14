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
        Orders blocks for single- and two-column pages. A block that crosses the page's midline
        (title, full-width paragraph, centred formula, table or figure) is full width. Full-width
        blocks cut the page into horizontal bands, and each band is read left column first, then
        right column. Classifying by width alone sent centred formulas and tables into a "column"
        and scrambled single-column pages.
        """
        if not raw_blocks:
            return []

        mid_x = page_width / 2.0
        gap = page_width * 0.02

        def top(block):
            try:
                return float(block[1])
            except Exception:
                return 0.0

        def centre(block, axis):
            try:
                return (float(block[axis]) + float(block[axis + 2])) / 2.0
            except Exception:
                return 0.0

        full_blocks, column_blocks = [], []
        for b in raw_blocks:
            try:
                spans_midline = float(b[0]) < mid_x - gap and float(b[2]) > mid_x + gap
            except Exception:
                spans_midline = True
            (full_blocks if spans_midline else column_blocks).append(b)

        full_blocks.sort(key=top)
        remaining = sorted(column_blocks, key=top)
        ordered = []
        for boundary in full_blocks + [None]:
            limit = top(boundary) if boundary is not None else float("inf")
            band = [b for b in remaining if centre(b, 1) < limit]
            remaining = [b for b in remaining if centre(b, 1) >= limit]
            ordered.extend(b for b in band if centre(b, 0) < mid_x)
            ordered.extend(b for b in band if centre(b, 0) >= mid_x)
            if boundary is not None:
                ordered.append(boundary)
        return ordered

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
        if re.search(r'equal contribution|alphabetical by given name|corresponding author|\*equal contribution|all authors contributed|work (was )?done (during|while|as|at)', t_low):
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

    # -------------------------------------------------------------------------
    # Translation scope, like Moonlight: the title, abstract, section headings, body prose and
    # formulas are translated. Front matter (authors, affiliations, keywords), tables, figures,
    # captions and references stay in the PDF view only.
    # -------------------------------------------------------------------------
    ABSTRACT_MARKER = re.compile(r'^abstract\s*($|[:.\-—–\n])', re.IGNORECASE)
    CAPTION_PATTERN = re.compile(r'^(figure|fig\.?|table|tab\.?)\s*([0-9]+|[IVXLC]+)\s*[:.|\n]', re.IGNORECASE)
    SUBFIGURE_CAPTION = re.compile(r'^\(([a-h]|[ivx]+)\)\s+\S')
    FRONT_MATTER_LABEL = re.compile(r'^(keywords|key words|index terms)\s*[:—–\-]', re.IGNORECASE)
    SECTION_NUMBER = re.compile(r'^(\d+(\.\d+)*\.?|[IVX]+\.?|[A-Z](\.\d+)*\.?)$')
    NUMBERED_HEADING = re.compile(r'^(\d+(\.\d+)*\.?|[IVX]+\.|[A-Z](\.\d+)*\.?)\s+[A-Z]')
    NAMED_HEADING = re.compile(r'^(introduction|related work|background|conclusions?|discussion|limitations|acknowledge?ments?)$', re.IGNORECASE)
    REFERENCES_HEADING = re.compile(r'^(\d+\.?\s*)?(references|bibliography)$', re.IGNORECASE)
    APPENDIX_HEADING = re.compile(r'^(?i:appendix|appendices)\b|^[A-Z](\.\d+)*\.?\s+[A-Z][A-Za-z0-9\- :&()]{2,80}$')

    # Display formulas: PDF text flattens their 2-D layout (fractions, big delimiters stored as CMEX glyph
    # codes), so a formula is kept as one region and shown as the original rendering instead of translated.
    MATH_FONT = re.compile(r'cmmi|cmsy|cmex|cmbsy|msbm|msam|eufm|eurm|eusm|rsfs|stmary|wasy|esint|lmmath|latinmodernmath|txmi|txsy|txex|pxmi|pxsy|pxex|ntxmi|ntxsy|ntxex|math|symbol', re.IGNORECASE)
    BIG_DELIMITER_FONT = re.compile(r'cmex|txex|pxex|ntxex', re.IGNORECASE)
    TEX_ROMAN_FONT = re.compile(r'^([A-Z]{6}\+)?(cmr|cmbx|cmti|cmsl|cmss|cmtt|lmroman)', re.IGNORECASE)
    UNICODE_MATH = re.compile('[Α-ω∀-⋿←-⇿⟀-⟯⦀-⧿\U0001d400-\U0001d7ff]')
    EQUATION_NUMBER = re.compile(r'^\(\s*[A-Z]?\.?\d+(\.\d+)*[a-z]?\s*\)$')

    @classmethod
    def _heading_text(cls, text: str) -> str:
        """A block's first line, joined with the next when PyMuPDF put the section number on its own line."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return ""
        if len(lines) > 1 and cls.SECTION_NUMBER.match(lines[0]):
            return f"{lines[0]} {lines[1]}"
        return lines[0]

    @classmethod
    def _is_section_heading(cls, text: str) -> bool:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        number_on_own_line = len(lines) > 1 and bool(cls.SECTION_NUMBER.match(lines[0]))
        heading = cls._heading_text(text)
        return (len(lines) == (2 if number_on_own_line else 1) and len(heading) <= 90
                and not heading.endswith((".", ":", ";", ","))
                and bool(cls.NUMBERED_HEADING.match(heading) or cls.NAMED_HEADING.match(heading)))

    @classmethod
    def _next_references_state(cls, text: str, in_references: bool) -> bool:
        heading = cls._heading_text(text)
        if cls.REFERENCES_HEADING.match(heading):
            return True
        if in_references and cls.APPENDIX_HEADING.match(heading):
            return False
        return in_references

    @classmethod
    def references_state_after_page(cls, page: Any, in_references: bool = False) -> bool:
        """Whether a references section is still open at the end of the page (it can span pages)."""
        for b in cls.sort_blocks_by_reading_flow(page.get_text("blocks"), page.rect.width):
            if len(b) > 4 and isinstance(b[4], str):
                in_references = cls._next_references_state(b[4].strip(), in_references)
        return in_references

    @staticmethod
    def _overlap_area(a: Any, b: Any) -> float:
        width = min(a[2], b[2]) - max(a[0], b[0])
        height = min(a[3], b[3]) - max(a[1], b[1])
        return width * height if width > 0 and height > 0 else 0.0

    @classmethod
    def _mostly_inside(cls, block: Any, region: Any) -> bool:
        area = max((block[2] - block[0]) * (block[3] - block[1]), 1e-6)
        return cls._overlap_area(block, region) > 0.5 * area

    @classmethod
    def _captioned_rule_tables(cls, page: Any, text_blocks: List[Any], drawings: List[Dict[str, Any]]) -> List[Any]:
        """
        Tables drawn with horizontal rules only (booktabs), which find_tables misses: start at the rule
        right below (or above) a "Table N" caption and follow rules of the same width until the next caption.
        """
        width, height = page.rect.width, page.rect.height
        rules = sorted({(round(d["rect"].y0, 1), d["rect"].x0, d["rect"].x1) for d in drawings
                        if d["rect"].height <= 2.5 and d["rect"].width >= 0.25 * width})

        def is_caption(block):
            return bool(cls.CAPTION_PATTERN.match(block[4].strip() + "\n"))

        regions = []
        for cap in (b for b in text_blocks if is_caption(b) and b[4].strip()[:3].lower() == "tab"):
            under_caption = [r for r in rules if min(cap[2], r[2]) > max(cap[0], r[1])]
            below = [r for r in under_caption if cap[3] - 2 <= r[0] <= cap[3] + 30]
            above = [r for r in under_caption if cap[1] - 30 <= r[0] <= cap[1] + 2]
            if not below and not above:
                continue
            downward = bool(below)
            chain = [below[0] if downward else above[-1]]
            for rule in (rules if downward else reversed(rules)):
                last = chain[-1]
                if (rule[0] <= last[0]) if downward else (rule[0] >= last[0]):
                    continue
                if abs(rule[0] - last[0]) > 0.5 * height:
                    break
                if abs(rule[1] - chain[0][1]) >= 25 or abs(rule[2] - chain[0][2]) >= 25:
                    continue
                low, high = sorted((last[0], rule[0]))
                if any(low < b[1] and b[3] < high + 1 and is_caption(b) for b in text_blocks):
                    break
                chain.append(rule)
            if len(chain) >= 2:
                ys = [r[0] for r in chain]
                regions.append((min(r[1] for r in chain), min(ys), max(r[2] for r in chain), max(ys)))
        return regions

    @classmethod
    def _non_prose_regions(cls, page: Any, text_blocks: List[Any]) -> Tuple[List[Any], List[Any]]:
        """(tables, figures) as (x0, y0, x1, y1) boxes. Pages without PyMuPDF drawing data have none."""
        if not hasattr(page, "get_drawings"):
            return [], []
        tables, figures = [], []
        try:
            tables += [tuple(t.bbox) for t in page.find_tables().tables]
        except Exception:
            pass
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        try:
            tables += cls._captioned_rule_tables(page, text_blocks, drawings)
        except Exception:
            pass
        try:
            for info in page.get_images(full=True):
                figures += [tuple(r) for r in page.get_image_rects(info[0]) if r.width > 30 and r.height > 30]
        except Exception:
            pass
        try:
            for cluster in page.cluster_drawings():
                box = tuple(cluster)
                # Images inside a diagram (icons, emoji) belong to it; only a table's rules are a different region.
                if cluster.width <= 60 or cluster.height <= 40 or any(cls._overlap_area(box, t) > 0 for t in tables):
                    continue
                # Lines have zero area, so count every stroke whose extent touches the cluster.
                strokes = sum(1 for d in drawings if d["rect"].x0 <= box[2] and d["rect"].x1 >= box[0]
                              and d["rect"].y0 <= box[3] and d["rect"].y1 >= box[1])
                text_area = sum(cls._overlap_area(b, box) for b in text_blocks)
                # Diagrams and charts have many strokes and little text; a formula or a boxed paragraph is text-dense.
                if strokes >= 8 and text_area <= 0.35 * cluster.get_area():
                    figures.append(box)
        except Exception:
            pass
        return tables, figures

    @classmethod
    def _is_figure_label(cls, text: str, block: Any, figures: List[Any]) -> bool:
        """Axis titles, legends and panel labels sit just outside a figure or a gridded chart that find_tables
        took for a table: short, unpunctuated text beside the region."""
        if len(text.split()) > 8 or re.search(r'[.!?;]$', text) or cls._is_section_heading(text):
            return False
        margin = 14.0
        return any(cls._overlap_area(block, (f[0] - margin, f[1] - margin, f[2] + margin, f[3] + margin)) > 0
                   for f in figures)

    @classmethod
    def _is_subfigure_caption(cls, text: str) -> bool:
        return bool(cls.SUBFIGURE_CAPTION.match(text)) and len(text.split()) <= 8

    @staticmethod
    def _bbox_key(box: Any) -> Tuple[float, ...]:
        return tuple(round(float(v), 1) for v in box[:4])

    @classmethod
    def _math_profiles(cls, page: Any) -> Dict[Tuple[float, ...], Dict[str, Any]]:
        """Per text block, keyed by bbox (dict numbering also counts image blocks): math share and words in text fonts."""
        try:
            layout = page.get_text("dict")
        except Exception:
            return {}
        if not isinstance(layout, dict):
            return {}
        profiles = {}
        for block in layout.get("blocks", []):
            if block.get("type") != 0:
                continue
            math_chars = text_chars = words = 0
            big_delimiter = False
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text, font = span.get("text", ""), span.get("font", "")
                    chars = [c for c in text if not c.isspace()]
                    if cls.MATH_FONT.search(font):
                        math_chars += len(chars)
                        big_delimiter = big_delimiter or (bool(chars) and bool(cls.BIG_DELIMITER_FONT.search(font)))
                        continue
                    words += len(re.findall(r'[A-Za-z]{3,}', text))
                    symbols = sum(1 for c in chars if cls.UNICODE_MATH.match(c))
                    math_chars += symbols
                    # TeX roman sets both prose and a formula's digits and operators, so it counts for neither side.
                    if not cls.TEX_ROMAN_FONT.search(font):
                        text_chars += len(chars) - symbols
            profiles[cls._bbox_key(block["bbox"])] = {
                "math_share": math_chars / max(math_chars + text_chars, 1),
                "math_chars": math_chars,
                "big_delimiter": big_delimiter,
                "words": words,
            }
        return profiles

    @classmethod
    def _equation_regions(cls, blocks: List[Any], profiles: Dict[Tuple[float, ...], Dict[str, Any]],
                          excluded: List[Any]) -> List[Dict[str, Any]]:
        """Display formulas as merged boxes: math-dominated blocks close together, small fragments, and the number."""
        pieces = []
        for b in blocks:
            text = str(b[4]).strip()
            profile = profiles.get(cls._bbox_key(b))
            if (not text or profile is None or cls._is_section_heading(text) or cls.CAPTION_PATTERN.match(text + "\n")
                    or any(cls._mostly_inside(b, region) for region in excluded)):
                continue
            seed = profile["words"] <= 4 and (profile["big_delimiter"] or profile["math_share"] >= 0.3
                                               or (profile["words"] <= 2 and profile["math_chars"] >= 3))
            number = bool(cls.EQUATION_NUMBER.match(text))
            fragment = profile["words"] <= 1 and len(text) <= 20
            if seed or number or fragment:
                pieces.append({"block": b, "seed": seed, "number": number})

        def near(box, other):
            return (other[1] <= box[3] + 8 and other[3] >= box[1] - 8
                    and max(box[0] - other[2], other[0] - box[2], 0) <= 20)

        def union(box, other):
            return (min(box[0], other[0]), min(box[1], other[1]), max(box[2], other[2]), max(box[3], other[3]))

        groups = [{"box": tuple(p["block"][:4]), "members": [p["block"]]} for p in pieces if p["seed"]]
        loose = [p for p in pieces if not p["seed"]]
        changed = True
        while changed:
            changed = False
            for group in groups:
                other = next((g for g in groups if g is not group and near(group["box"], g["box"])), None)
                if other is not None:
                    group["box"] = union(group["box"], other["box"])
                    group["members"] += other["members"]
                    groups.remove(other)
                    changed = True
                    break
            if changed:
                continue
            for piece in [p for p in loose if not p["number"]]:
                group = next((g for g in groups if near(g["box"], piece["block"])), None)
                if group is not None:
                    group["box"] = union(group["box"], piece["block"])
                    group["members"].append(piece["block"])
                    loose.remove(piece)
                    changed = True
        # An equation number sits at the right margin, often far from the formula itself.
        for piece in [p for p in loose if p["number"]]:
            b = piece["block"]
            centre = (b[1] + b[3]) / 2.0
            options = [g for g in groups if g["box"][1] - 4 <= centre <= g["box"][3] + 4 and b[0] >= g["box"][0]]
            if options:
                group = min(options, key=lambda g: b[0] - g["box"][2])
                group["box"] = union(group["box"], b)
                group["members"].append(b)
        return groups

    @classmethod
    def _could_be_title(cls, block: Any) -> bool:
        text = str(block[4]).strip()
        vertical_margin_stamp = (block[2] - block[0]) < 35 and (block[3] - block[1]) > 60
        return len(text) >= 5 and not vertical_margin_stamp and not cls.is_noise_or_meta(text)

    @classmethod
    def extract_aligned_page_blocks(
        cls,
        doc_or_page: Any,
        page_idx: int = 0,
        crop_rect: Any = None,
        in_references: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extracts the translatable paragraphs of a page in reading order, with bounding boxes relative
        to crop_rect: title, abstract, section headings, body prose and formulas. Front matter, tables,
        figures, captions and references are left out. in_references tells whether a references
        section opened on an earlier page is still running.
        """
        if doc_or_page is None:
            return [], []

        page = doc_or_page if not hasattr(doc_or_page, "open") else doc_or_page[page_idx]
        actual_crop = crop_rect if crop_rect is not None else page.rect

        raw_blocks = [b for b in page.get_text("blocks") if len(b) < 7 or b[6] == 0]
        tables, figures = cls._non_prose_regions(page, raw_blocks)
        # Each display formula replaces its fragments with one block covering the whole formula.
        formulas = cls._equation_regions(raw_blocks, cls._math_profiles(page), tables + figures)
        fragment_keys = {cls._bbox_key(m) for f in formulas for m in f["members"]}
        formula_blocks = [(*f["box"], " ".join(" ".join(str(m[4]).split()) for m in sorted(f["members"], key=lambda m: (m[1], m[0]))), -1, 0)
                          for f in formulas]
        formula_keys = {cls._bbox_key(f) for f in formula_blocks}
        sorted_blocks = cls.sort_blocks_by_reading_flow(
            [b for b in raw_blocks if cls._bbox_key(b) not in fragment_keys] + formula_blocks, page.rect.width)

        # Front matter: on the first page, everything before the abstract except the title.
        abstract_index = title_index = None
        if getattr(page, "number", 0) == 0:
            abstract_index = next((i for i, b in enumerate(sorted_blocks)
                                   if cls.ABSTRACT_MARKER.match(str(b[4]).strip())), None)
            if abstract_index is not None:
                title_index = next((i for i, b in enumerate(sorted_blocks[:abstract_index]) if cls._could_be_title(b)), None)

        candidate_items = []
        is_in_abstract = False
        previous_caption = None

        for index, b in enumerate(sorted_blocks):
            try:
                text = b[4].strip()
            except Exception:
                continue

            in_references = cls._next_references_state(text, in_references)
            if in_references:
                continue
            if abstract_index is not None and index < abstract_index and index != title_index:
                continue
            is_title = index == title_index
            if cls._bbox_key(b) in formula_keys:
                previous_caption = None
                candidate_items.append({"text": text, "rect": cls.create_rect(b[0], b[1], b[2], b[3]),
                                        "is_abstract": False, "is_heading": False, "is_equation": True})
                continue
            if any(cls._mostly_inside(b, region) for region in tables + figures):
                continue
            rect = cls.create_rect(b[0], b[1], b[2], b[3])
            caption_continues = (previous_caption is not None and 0 <= rect.y0 - previous_caption.y1 <= 3
                                 and min(rect.x1, previous_caption.x1) - max(rect.x0, previous_caption.x0) > 0.5 * max(rect.x1 - rect.x0, 1e-6))
            if cls.CAPTION_PATTERN.match(text + "\n") or cls._is_subfigure_caption(text) or caption_continues:
                previous_caption = rect
                continue
            previous_caption = None
            if cls.FRONT_MATTER_LABEL.match(text) or (not is_title and cls._is_figure_label(text, b, tables + figures)):
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

            if not is_title and (cls.is_noise_or_meta(text) or cls.is_figure_table_caption_or_chart(text)):
                continue

            is_heading = cls._is_section_heading(text)
            clean_p = cls._heading_text(text) if is_heading else cls.clean_academic_text(text)

            # Guard mathematical formulas and numbered equations from being dropped by the length filter
            has_math_indicators = bool(re.search(r'[=∑∫∏∇∂±×÷≈≠≤≥∈∉⊂⊆∪∩→←⇒↔∞√]|\\\\|\\^|_\{|\$|\b(?:alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|tau|phi|psi|omega)\b', clean_p, flags=re.IGNORECASE))
            has_equation_number = bool(re.search(r'\(\s*\d+\s*\)\s*$', clean_p))

            if len(clean_p) < 15 and not (has_math_indicators or has_equation_number or is_heading):
                continue

            had_abstract_prefix = bool(re.match(r'^abstract\s*[:\.\-—–]?\s*', clean_p, flags=re.IGNORECASE))
            if had_abstract_prefix:
                clean_p = re.sub(r'^abstract\s*[:\.\-—–]?\s*', '', clean_p, flags=re.IGNORECASE).strip()
                is_in_abstract = True
                if not clean_p:
                    continue

            candidate_items.append({
                "text": clean_p,
                "rect": rect,
                "is_abstract": is_in_abstract,
                "is_heading": is_heading
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

            if (prev_is_numbered_eq or curr_is_numbered_eq or prev_is_short_math or curr_is_short_math
                    or prev.get("is_heading") or item.get("is_heading") or prev.get("is_equation") or item.get("is_equation")):
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
                "raw_rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                "kind": "equation" if item.get("is_equation") else ("heading" if item.get("is_heading") else "text")
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
        Renders a single precision bounding box with Luminous Neon Glow and animated pulse;
        hover and click are handled by the delegated reader controller.
        """
        top = bbox.get("top", "0%")
        left = bbox.get("left", "0%")
        w = bbox.get("width", "0%")
        h = bbox.get("height", "0%")
        safe_hint = html.escape(title_hint or f"원문 단락 [{pair_id}]")

        # Hover and click sync comes from the delegated reader controller through data-id. Streamlit
        # renders markdown with React, which rejects string event attributes (error #231 on every hover).
        return (
            f'<div id="pdf-hl-{pair_id}" data-id="{pair_id}" class="pdf-highlight-overlay" '
            f'style="top:{top}; left:{left}; width:{w}; height:{h};" '
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

    @staticmethod
    def _formula_image_html(pair: Dict[str, Any]) -> str:
        """The formula as the PDF renders it; its text layer cannot rebuild the 2-D layout."""
        path = pair.get("image_path")
        if not path or not os.path.exists(path):
            return '<div class="doc-formula-missing">수식 이미지를 불러오지 못했어요. 원문에서 확인해 주세요.</div>'
        with open(path, "rb") as image:
            data = base64.b64encode(image.read()).decode("ascii")
        width = float(pair.get("image_width_pt") or 0) * 1.5
        size = f' style="width:{width:.0f}px"' if width else ""
        return (f'<div class="doc-formula-frame"><img class="doc-formula-image" src="data:image/png;base64,{data}"'
                f' alt="수식 원본"{size}></div>')

    @classmethod
    def render_translation_paragraphs(
        cls,
        pairs: List[Dict[str, Any]],
        current_page: int,
        font_size: int = 16,
        line_height: float = 1.85
    ) -> str:
        """
        Builds the right-side scrollable Korean translation pane.

        Streamlit renders Markdown math with its bundled KaTeX, but not inside a raw HTML block. Each
        paragraph's div therefore ends its line and is followed by a blank line, so the body is parsed as
        Markdown (formulas render, prose is escaped) inside the wrapper. Hover and click sync comes from
        the delegated reader controller through data-id; Streamlit strips inline event attributes.
        """
        page = html.escape(str(current_page))
        frame = (f'<div class="unified-reader-frame" key="trans-frame-{page}">\n'
                 f'<div class="scrollable-trans-box" id="trans-scroll-pane-{page}">\n')
        if not pairs:
            return (frame + '<div style="color: #86868B; padding: 1.5rem;">'
                    '이 페이지에는 텍스트 본문이 없습니다 (도표 또는 수식 전용).</div>\n</div>\n</div>')

        para_style = f"font-size: {int(font_size)}px; line-height: {float(line_height)};"
        paragraphs = []
        for idx, pair in enumerate(pairs):
            p_id = html.escape(str(pair.get("id", idx + 1)))
            if pair.get("kind") == "equation":
                paragraphs.append(
                    f'<div class="doc-para doc-formula" style="{para_style}" id="para-item-{p_id}" data-id="{p_id}">\n\n'
                    f'<span class="doc-para-idx">[{p_id}]</span>\n\n{cls._formula_image_html(pair)}\n\n</div>'
                )
                continue
            body = AcademicMathFormatter.to_markdown(str(pair.get("ko") or "").strip())
            # A paragraph that opens with display math keeps it on its own block.
            gap = "\n\n" if body.startswith("$$") else " "
            paragraphs.append(
                f'<div class="doc-para" style="{para_style}" id="para-item-{p_id}" data-id="{p_id}">\n\n'
                f'<span class="doc-para-idx">[{p_id}]</span>{gap}{body}\n\n</div>'
            )
        return frame + "\n".join(paragraphs) + "\n</div>\n</div>"

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
        background-color: #EEF1DF !important;
        border-left: 4px solid #3F5947 !important;
        box-shadow: 0 4px 16px rgba(0, 113, 227, 0.12) !important;
        color: #39392E !important;
    }

    .doc-para.pinned {
        background-color: #E3EBD4 !important;
        border-left: 5px solid #476249 !important;
        box-shadow: 0 4px 20px rgba(0, 113, 227, 0.25) !important;
        color: #39392E !important;
    }

    .doc-para-idx {
        font-weight: 800 !important;
        color: #3F5947 !important;
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
