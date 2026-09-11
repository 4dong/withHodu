"""
Academic Mathematical Formula Formatter & LaTeX/KaTeX Normalizer
Transforms raw PDF OCR/Neural translation math symbols into clean, renderable LaTeX notation ($...$ and $$...$$).
Provides robust HTML escaping that protects mathematical equations for pixel-perfect KaTeX rendering.
"""

import re
import html
from typing import List, Dict, Any, Optional

class AcademicMathFormatter:
    """
    Normalizes broken math tokens, Greek phonetics, and equations into standard KaTeX/LaTeX format,
    and safely prepares text for HTML rendering without corrupting mathematical notation.
    """

    # Comprehensive Greek phonetic mappings to LaTeX command
    GREEK_MAP = [
        (r"알파", r"\alpha"),
        (r"베타", r"\beta"),
        (r"감마", r"\gamma"),
        (r"델타", r"\delta"),
        (r"엡실론|입실론", r"\epsilon"),
        (r"제타", r"\zeta"),
        (r"에타", r"\eta"),
        (r"세타|쎄타", r"\theta"),
        (r"요타", r"\iota"),
        (r"카파", r"\kappa"),
        (r"람다", r"\lambda"),
        (r"뮤", r"\mu"),
        (r"뉴", r"\nu"),
        (r"크사이|자이", r"\xi"),
        (r"파이", r"\pi"),
        (r"로우", r"\rho"),
        (r"시그마", r"\sigma"),
        (r"타우", r"\tau"),
        (r"위프실론", r"\upsilon"),
        (r"파이값|변수\s*피", r"\phi"),
        (r"카이", r"\chi"),
        (r"프사이", r"\psi"),
        (r"오메가", r"\omega"),
    ]

    # Math unicode symbol to LaTeX mapping
    UNICODE_MATH_MAP = {
        "±": r"\pm",
        "×": r"\times",
        "÷": r"\div",
        "·": r"\cdot",
        "≈": r"\approx",
        "≠": r"\neq",
        "≤": r"\leq",
        "≥": r"\geq",
        "≪": r"\ll",
        "≫": r"\gg",
        "∈": r"\in",
        "∉": r"\notin",
        "⊂": r"\subset",
        "⊆": r"\subseteq",
        "∪": r"\cup",
        "∩": r"\cap",
        "→": r"\to",
        "←": r"\leftarrow",
        "⇒": r"\Rightarrow",
        "⇐": r"\Leftarrow",
        "↔": r"\leftrightarrow",
        "∇": r"\nabla",
        "∂": r"\partial",
        "∞": r"\infty",
        "∑": r"\sum",
        "∏": r"\prod",
        "∫": r"\int",
        "√": r"\sqrt",
    }

    @classmethod
    def format_math_in_text(cls, text: str) -> str:
        """
        Processes Korean/English translation text and converts embedded math formulas into clean KaTeX syntax.
        Defensively handles None or non-string inputs.
        """
        if not text or not isinstance(text, str):
            return ""

        # 0. Defensive Unicode Normalization (dash, quote, circumflex)
        res = text.replace("−", "-").replace("–", "-").replace("“", '"').replace("”", '"').replace("ˆ", "^")
        res = re.sub(r"\^([a-zA-Z0-9]+)\s*\n\s*([0-9]+)", r"^\1 \2", res)
        res = re.sub(r"(?<=[a-zA-Z0-9=\+\-\(\)\{\}\^])\s*\n\s*(?=[a-zA-Z0-9=\+\-\(\)\{\}\^])", " ", res)

        # 1. Detect and convert full complex equation lines first
        res = cls._normalize_complex_equations(res)

        # 2. Split text by existing $$...$$ and $...$ to avoid corrupting already formatted math
        tokens = re.split(r"(\$\$[\s\S]*?\$\$|\$[^\$\n]+?\$)", res)
        processed_tokens = []

        for token in tokens:
            if not token:
                continue
            if token.startswith("$"):
                # Already LaTeX math -> clean internal whitespace, command escapes, and brackets
                clean_m = cls._clean_inner_math(token)
                processed_tokens.append(clean_m)
            else:
                # Text segment -> apply smart academic math transforms
                t = cls._transform_text_segment(token)
                processed_tokens.append(t)

        out = "".join(processed_tokens)
        return cls._cleanup_math_delimiters(out)

    @classmethod
    def escape_html_outside_math(cls, text: str) -> str:
        """
        Safely escapes HTML special characters outside math delimiters ($...$, $$...$$).
        Preserves raw LaTeX characters (<, >, &, ', ") inside formulas so KaTeX can render flawlessly.
        """
        if not text or not isinstance(text, str):
            return ""

        # Split into math blocks and non-math text
        tokens = re.split(r"(\$\$[\s\S]*?\$\$|\$[^\$\n]+?\$)", text)
        result_parts = []

        for token in tokens:
            if not token:
                continue
            if token.startswith("$"):
                # Math formula -> Unescape any previously escaped HTML entities inside LaTeX, keep raw formula
                math_content = html.unescape(token)
                # Defensively sanitize any malicious script injection tags
                math_content = re.sub(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", "", math_content, flags=re.IGNORECASE)
                result_parts.append(math_content)
            else:
                # Normal text -> Standard HTML escaping for safety
                escaped_text = html.escape(token, quote=False)
                result_parts.append(escaped_text)

        return "".join(result_parts)

    @classmethod
    def _clean_inner_math(cls, math_token: str) -> str:
        """Sanitizes inner LaTeX math strings, fixing broken backslashes and spacing."""
        if not math_token:
            return ""
        
        is_display = math_token.startswith("$$") and math_token.endswith("$$")
        inner = math_token[2:-2] if is_display else math_token[1:-1]
        
        # Clean broken backslashes or spaced commands (e.g. \ theta -> \theta, \ sigma -> \sigma)
        inner = re.sub(
            r'\\\s+(theta|sigma|Delta|lambda|alpha|beta|gamma|mu|nu|xi|pi|rho|tau|phi|chi|psi|omega|epsilon|zeta|eta|kappa|iota|upsilon|Gamma|Theta|Lambda|Xi|Pi|Sigma|Phi|Psi|Omega|hat|frac|text|quad|mathbf|mathcal|mathbb|operatorname|sqrt|sum|prod|int|partial|nabla|approx|leq|geq|in|notin|subset|subseteq|pm|times|cdot|to|leftarrow|Rightarrow|Leftarrow|log|ln|exp|det|tr|min|max|arg)',
            r'\\\1',
            inner
        )

        # Fix detached subscript/superscript spacing inside LaTeX: x _ t -> x_t, w ^ 2 -> w^2
        inner = re.sub(r'([a-zA-Z0-9\}])\s*_\s*([a-zA-Z0-9\{])', r'\1_\2', inner)
        inner = re.sub(r'([a-zA-Z0-9\}])\s*\^\s*([a-zA-Z0-9\{])', r'\1^\2', inner)

        # Wrap back in delimiters
        return f"$${inner}$$" if is_display else f"${inner}$"

    @classmethod
    def _transform_text_segment(cls, text: str) -> str:
        """Transforms broken academic symbols, Greek phonetics, and math expressions into LaTeX notation."""
        t = text

        # 1. Unicode Math Symbols normalization
        for sym, lat in cls.UNICODE_MATH_MAP.items():
            if sym in t:
                t = t.replace(sym, f" {lat} ")

        # 1. Variance / SDE / Diffusion terms (Highest precedence to avoid partial word split)
        t = re.sub(r"(?:[σ]|\\\\sigma|sigma)\s*2\s*t\s*2\s*\(\s*1\s*-\s*t\s*\)", r"$\\sigma^2 t^2(1 - t)$", t)
        t = re.sub(r"(?:[σ]|\\\\sigma|sigma)\s*\^\s*2\s*t\s*\^\s*2\s*\(\s*1\s*-\s*t\s*\)", r"$\\sigma^2 t^2(1 - t)$", t)

        # 2. Hat and Subscript tokens (e.g. ^xi 1 -> $\hat{x}_1^i$, ^Ai -> $\hat{A}^i, ^x -> $\hat{x}$)
        t = re.sub(r"\^([a-z])([a-z0-9])\s*(\d+)", lambda m: f"$\\hat{{{m.group(1)}}}_{{{m.group(3)}}}^{{{m.group(2)}}}$", t)
        t = re.sub(r"\^([A-Z])([a-z0-9])", lambda m: f"$\\hat{{{m.group(1)}}}^{{{m.group(2)}}}$", t)
        t = re.sub(r"\^([a-zA-Z])\b", lambda m: f"$\\hat{{{m.group(1)}}}$", t)

        # 3. Velocity / Flow Matching / Score condition functions
        t = re.sub(r"\bv[\s_]*(?:\{?\s*(?:θ|\\\\theta|_\theta|세타|theta)\s*\}?)\s*\(\s*x\s*t?\s*,\s*t\s*\)", r"$v_\\theta(x_t, t)$", t)
        t = re.sub(r"\bv[\s_]*(?:\{?\s*(?:θ|\\\\theta|_\theta|세타|theta)\s*\}?)\b", r"$v_\\theta$", t)
        t = re.sub(r"\bu\s*\(\s*x\s*t?\s*,\s*t\s*\)", r"$u(x_t, t)$", t)

        # 4. Loss functions & Expectations
        t = re.sub(r"\bL\s*\(\s*(?:θ|\\\\theta|세타|theta)\s*\)", r"$\\mathcal{L}(\\theta)$", t)
        t = re.sub(r"\bL_\s*(?:total|loss|gen|disc|reg|rec)\b", lambda m: f"$\\mathcal{{L}}_{{\\text{{{m.group(0).split('_')[1]}}}}}$", t)
        t = re.sub(r"\bE\s*\[\s*\|\|\s*", r"$\\mathbb{E}[\\|", t)

        # 5. Delta time terms (Single unified transform with dollar lookaround guard)
        t = re.sub(
            r"(?<![a-zA-Z0-9\$\\])\b(?:[Δ]|Delta|델타)\s*([a-zA-Z0-9]+)\b(?![a-zA-Z0-9\$])",
            lambda m: f"$\\Delta {m.group(1)}$",
            t
        )
        t = re.sub(
            r"(?<![a-zA-Z0-9\$\\])\b(?:[Δ]|Delta|델타)\b(?![a-zA-Z0-9\$])",
            r"$\\Delta$",
            t
        )

        # 6. Real Euclidean Space & Distributions
        t = re.sub(r"\bR\s*\^\s*([0-9a-zA-Z\+]+)", lambda m: f"$\\mathbb{{R}}^{{{m.group(1)}}}$", t)
        t = re.sub(r"\bN\s*\(\s*(?:0|\\\\mu|μ|mu)\s*,\s*(?:I|\\\\sigma\^2|σ\^2|sigma\^2|1)\s*\)", lambda m: f"$\\mathcal{{N}}({m.group(0)[2:-1]})$", t)

        # 7. Comprehensive Greek Phonetics with Subscripts/Numbers
        for kr_pat, lat_cmd in cls.GREEK_MAP:
            t = re.sub(
                rf"(?<![가-힣])(?:{kr_pat})\s*(\d+)\s*,\s*(?:{kr_pat})\s*(\d+)\s*,\s*(?:{kr_pat})\s*(\d+)",
                lambda m, cmd=lat_cmd: f"${cmd}_{{{m.group(1)}}}, {cmd}_{{{m.group(2)}}}, {cmd}_{{{m.group(3)}}}$",
                t
            )
            t = re.sub(
                rf"(?<![가-힣])(?:{kr_pat})\s*(\d+)\s*,\s*(?:{kr_pat})\s*(\d+)",
                lambda m, cmd=lat_cmd: f"${cmd}_{{{m.group(1)}}}, {cmd}_{{{m.group(2)}}}$",
                t
            )
            t = re.sub(
                rf"(?<![가-힣])(?:{kr_pat})\s*_?\s*([0-9a-zA-Z]+)(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))",
                lambda m, cmd=lat_cmd: f"${cmd}_{{{m.group(1)}}}$",
                t
            )
            t = re.sub(
                rf"(?<![가-힣])(?:{kr_pat})(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))",
                lambda m, cmd=lat_cmd: f"${cmd}$",
                t
            )

        # 8. English Greek letter words from raw Google translation
        ENG_GREEK_WORDS = [
            (r"alpha", r"\alpha"),
            (r"beta", r"\beta"),
            (r"gamma", r"\gamma"),
            (r"delta", r"\delta"),
            (r"epsilon", r"\epsilon"),
            (r"zeta", r"\zeta"),
            (r"eta", r"\eta"),
            (r"theta", r"\theta"),
            (r"iota", r"\iota"),
            (r"kappa", r"\kappa"),
            (r"lambda", r"\lambda"),
            (r"mu", r"\mu"),
            (r"nu", r"\nu"),
            (r"xi", r"\xi"),
            (r"rho", r"\rho"),
            (r"sigma", r"\sigma"),
            (r"tau", r"\tau"),
            (r"upsilon", r"\upsilon"),
            (r"phi", r"\phi"),
            (r"chi", r"\chi"),
            (r"psi", r"\psi"),
            (r"omega", r"\omega"),
        ]
        for eng_w, lat_c in ENG_GREEK_WORDS:
            t = re.sub(
                rf"(?<![a-zA-Z0-9\$\\]){eng_w}\s*_?\s*([0-9a-zA-Z]+)(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))(?![a-zA-Z0-9\$])",
                lambda m, cmd=lat_c: f"${cmd}_{{{m.group(1)}}}$",
                t
            )
            t = re.sub(
                rf"(?<![a-zA-Z0-9\$\\]){eng_w}(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))(?![a-zA-Z0-9\$])",
                lambda m, cmd=lat_c: f"${cmd}$",
                t
            )

        # 9. Capital Greek letters
        t = re.sub(r"(?<![가-힣\$\\])델타\s*_?\s*([A-Za-z0-9]+)?(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))", lambda m: f"$\\Delta_{{{m.group(1)}}}$" if m.group(1) else r"$\\Delta$", t)
        t = re.sub(r"(?<![가-힣\$\\])대문자\s*감마(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))", r"$\\Gamma$", t)
        t = re.sub(r"(?<![가-힣\$\\])대문자\s*시그마(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))", r"$\\Sigma$", t)
        t = re.sub(r"(?<![가-힣\$\\])대문자\s*오메가(?=(?:[은는이가을를의와과에로으로](?:[,\.\?!\s]|$)|[,\.\?!\s]|$))", r"$\\Omega$", t)

        # 10. Subscript variable pairs (e.g. W_q는 -> $W_{q}$는, x_t -> $x_t$)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])([a-zA-Z])\s*_\s*([0-9a-zA-Z]+)(?=[은는이가을를의와과에로으로]|\s|[,\.\?!]|\b|$)(?![a-zA-Z0-9\$])", lambda m: f"${m.group(1)}_{{{m.group(2)}}}$", t)
        t = re.sub(r"\bxt\s*,\s*(?:평균|mean)", r"$x_{t,\\text{mean}}$", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])xt(?=[은는이가을를의와과에로으로]|\s|[,\.\?!]|\b|$)(?![a-zA-Z0-9\$])", r"$x_t$", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])x0(?=[은는이가을를의와과에로으로]|\s|[,\.\?!]|\b|$)(?![a-zA-Z0-9\$])", r"$x_0$", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])x1(?=[은는이가을를의와과에로으로]|\s|[,\.\?!]|\b|$)(?![a-zA-Z0-9\$])", r"$x_1$", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])xT(?=[은는이가을를의와과에로으로]|\s|[,\.\?!]|\b|$)(?![a-zA-Z0-9\$])", r"$x_T$", t)

        # 11. Common isolated math variables before Korean particles (e.g. x는 -> $x$는)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])([a-zA-Z])\s*(는|은|를|을|의|에|가|와|과|로|으로)(?=\s|$|[,\.\?!])(?![a-zA-Z0-9\$])", lambda m: f"${m.group(1)}${m.group(2)}", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])([ijknt])\s*번째\b", lambda m: f"${m.group(1)}$번째", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])([dDkKnN])\s*차원\b", lambda m: f"${m.group(1)}$차원", t)
        t = re.sub(r"(?<![a-zA-Z0-9\$\\])([GKM])\s*(파형|샘플|그룹|개|스텝|단계)\b", lambda m: f"${m.group(1)}$ {m.group(2)}", t)

        # 12. Norms and distances
        t = re.sub(r"\|\|\s*([^\|]+?)\s*\|\|\s*\^\s*(\d+)", lambda m: f"$\\|{m.group(1)}\\|^{{{m.group(2)}}}$", t)

        return t

    @classmethod
    def _normalize_complex_equations(cls, text: str) -> str:
        """Detects standard academic normalization, flow matching, and fraction formulas and converts to full LaTeX."""
        # 1. Normalization / Advantage formula e.g. A^i = (R - mean) / std
        pattern_norm = re.compile(
            r"\^?A\s*i?\s*=\s*R\s*\(\s*\^?x\s*i?\s*1?\s*,\s*c\s*\)\s*-\s*(?:평균|mean)\s*\{([^}]+)\}\s*G?\s*j?\s*=\s*1\s*(?:std|표준편차)\s*\{([^}]+)\}\s*G?\s*j?\s*=\s*1\s*(?:\.\s*)?(\(\d+\))?",
            re.IGNORECASE
        )
        def repl_norm(m):
            eq_num = m.group(3) or ""
            eq_num_str = f" \\quad {eq_num}" if eq_num else ""
            return f"$$\\hat{{A}}^i = \\frac{{R(\\hat{{x}}_1^i, c) - \\text{{mean}}\\{{R(\\hat{{x}}_1^j, c)\\}}_j^G}}{{\\text{{std}}\\{{R(\\hat{{x}}_1^j, c)\\}}_j^G}}{eq_num_str}$$"

        text = pattern_norm.sub(repl_norm, text)

        # 2. SDE / Flow matching trajectory mean formula
        pattern_sde = re.compile(
            r"xt\s*,\s*(?:평균|mean)\s*=\s*xt\s*\+\s*(?:vθ|v\\\\theta|v_\theta|v|v세타)\s*\(\s*xt\s*,\s*t\s*\)\s*\+\s*(?:σ|\\\\sigma)?\s*2\s*t\s*2\s*\(\s*1\s*-\s*t\s*\)\s*\(\s*-\s*xt\s*\+\s*t\s*(?:vθ|v\\\\theta|v_\theta|v|v세타)\s*\(\s*xt\s*,\s*t\s*\)\s*\)\s*(?:Δ|\\\\Delta|델타)?\s*t\s*,?\s*(\(\d+\))?",
            re.IGNORECASE
        )
        def repl_sde(m):
            eq_num = m.group(1) or ""
            eq_num_str = f" \\quad {eq_num}" if eq_num else ""
            return f"$$x_{{t,\\text{{mean}}}} = x_t + v_\\theta(x_t, t) + \\sigma^2 t^2(1 - t)(-x_t + t v_\\theta(x_t, t)) \\Delta t{eq_num_str}$$"

        text = pattern_sde.sub(repl_sde, text)

        # 3. Standard Loss function equation lines (e.g. L(theta) = E[ ... ] (4))
        pattern_loss = re.compile(
            r"(?:손실\s*함수|Loss\s*Function)?\s*L\s*\(\s*(?:θ|\\\\theta|세타)\s*\)\s*=\s*E\s*\[\s*\|\|\s*v\s*(?:θ|\\\\theta|_\theta|세타)\s*\(\s*xt\s*,\s*t\s*\)\s*-\s*u\s*\|\|\s*\^?\s*2\s*\]\s*(\(\d+\))?",
            re.IGNORECASE
        )
        def repl_loss(m):
            eq_num = m.group(1) or ""
            eq_num_str = f" \\quad {eq_num}" if eq_num else ""
            return f"$$\\mathcal{{L}}(\\theta) = \\mathbb{{E}}_{{t, x_0, x_1}} [ \\| v_\\theta(x_t, t) - u(x_t, t) \\|^2 ]{eq_num_str}$$"

        text = pattern_loss.sub(repl_loss, text)

        return text

    @classmethod
    def _cleanup_math_delimiters(cls, text: str) -> str:
        """Cleans up overlapping, malformed, or redundant $ delimiters without corrupting $$ display math."""
        if not text:
            return ""
        # 3 or more $ -> $$
        text = re.sub(r"\${3,}", "$$", text)
        # Fix adjacent inline delimiters e.g. $ + $ between single dollars only
        text = re.sub(r"(?<!\$)\$\s*,\s*\$(?!\$)", ", ", text)
        text = re.sub(r"(?<!\$)\$\s*\+\s*\$(?!\$)", " + ", text)
        text = re.sub(r"(?<!\$)\$\s*-\s*\$(?!\$)", " - ", text)
        text = re.sub(r"(?<!\$)\$\s*=\s*\$(?!\$)", " = ", text)
        # Remove empty inline math with spaces `$ $`, preserving `$$`
        text = re.sub(r"(?<!\$)\$\s+\$(?!\$)", "", text)
        return text

