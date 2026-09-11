"""
Comprehensive Unit tests for AcademicMathFormatter & LaTeX/KaTeX normalizer
Tests normalization coverage, idempotency, false-positive elimination, and prompt-formatter alignment.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.math_formatter import AcademicMathFormatter

def test_greek_phonetics():
    # 1. Greek phonetic lists and subscripts
    raw1 = "학습률 람다 1, 람다 2, 람다 3을 설정하고 손실을 최소화한다."
    res1 = AcademicMathFormatter.format_math_in_text(raw1)
    assert r"$\lambda_{1}, \lambda_{2}, \lambda_{3}$" in res1, f"Failed: {res1}"

    raw2 = "모델 파라미터 세타는 그래디언트를 따라 업데이트된다."
    res2 = AcademicMathFormatter.format_math_in_text(raw2)
    assert r"$\theta$" in res2, f"Failed: {res2}"

    raw3 = "표준편차 시그마_t와 분산 sigma2 t 2(1 -t)를 적용한다."
    res3 = AcademicMathFormatter.format_math_in_text(raw3)
    assert r"$\sigma_{t}$" in res3, f"Failed: {res3}"
    assert r"$\sigma^2 t^2(1 - t)$" in res3, f"Failed: {res3}"

def test_false_positive_elimination():
    # 2. Prevent corrupting normal Korean words containing phonetic syllables
    test_words = "데이터셋을 기반으로 커뮤니티와 메뉴를 제공하며 스타일과 그래디언트로 학습한다. 반면 세타는 파라미터이고 람다1과 알파는 가중치이다."
    res = AcademicMathFormatter.format_math_in_text(test_words)
    assert "메뉴" in res, f"메뉴 corrupted: {res}"
    assert "커뮤니티" in res, f"커뮤니티 corrupted: {res}"
    assert "기반으로" in res, f"기반으로 corrupted: {res}"
    assert "그래디언트로" in res, f"그래디언트로 corrupted: {res}"
    assert "스타일" in res, f"스타일 corrupted: {res}"
    assert "데이터셋" in res, f"데이터셋 corrupted: {res}"
    assert r"$\theta$는" in res, f"세타 missing: {res}"
    assert r"$\lambda_{1}$" in res, f"람다1 missing: {res}"
    assert r"$\alpha$" in res, f"알파 missing: {res}"

def test_complex_academic_equations():
    # 3. SDE & Flow matching equation
    raw_sde = "xt, 평균 = xt + vθ(xt, t) + σ2 t 2(1 - t)(-xt + t vθ(xt, t)) Δt (5)"
    res_sde = AcademicMathFormatter.format_math_in_text(raw_sde)
    assert r"$$x_{t,\text{mean}} = x_t + v_\theta(x_t, t) + \sigma^2 t^2(1 - t)(-x_t + t v_\theta(x_t, t)) \Delta t \quad (5)$$" in res_sde, f"Failed: {res_sde}"

    # 4. Advantage normalization formula
    raw_norm = "^Ai = R(^xi 1, c) - 평균{R(^xj 1, c)} G j=1 std{R(^xj 1, c)} G j=1 (6)"
    res_norm = AcademicMathFormatter.format_math_in_text(raw_norm)
    assert r"$$\hat{A}^i = \frac{R(\hat{x}_1^i, c) - \text{mean}\{R(\hat{x}_1^j, c)\}_j^G}{\text{std}\{R(\hat{x}_1^j, c)\}_j^G} \quad (6)$$" in res_norm, f"Failed: {res_norm}"

    # 5. Loss function equation
    raw_loss = "Loss Function L(θ) = E[ || vθ(xt, t) - u ||^2 ] (4)"
    res_loss = AcademicMathFormatter.format_math_in_text(raw_loss)
    assert r"$$\mathcal{L}(\theta) = \mathbb{E}_{t, x_0, x_1} [ \| v_\theta(x_t, t) - u(x_t, t) \|^2 ] \quad (4)$$" in res_loss, f"Failed: {res_loss}"

def test_html_escape_outside_math():
    # 6. HTML escaping with math symbols preservation (<, >, &, ', ")
    text = "조건 <script>alert(1)</script> 에서 수식 $x < y$ 와 $a > b$ 및 $f'(x) & g(x)$ 를 만족하고, 문맥은 <b>중요</b>하다."
    escaped = AcademicMathFormatter.escape_html_outside_math(text)
    
    assert "<script>" not in escaped
    assert "&lt;b&gt;중요&lt;/b&gt;" in escaped
    assert "$x < y$" in escaped, f"Math < corrupted: {escaped}"
    assert "$a > b$" in escaped, f"Math > corrupted: {escaped}"
    assert "$f'(x) & g(x)$" in escaped, f"Math & or ' corrupted: {escaped}"

def test_idempotency_alignment():
    # 7. Formatter must be strictly idempotent when applied multiple times
    text = "우리는 손실 함수 $\\mathcal{L}(\\theta)$를 최소화하며, 상태 변수 $x_t$와 속도 벡터 $v_\\theta(x_t, t)$에 대해 $\\Delta t$ 간격으로 적분한다."
    step1 = AcademicMathFormatter.format_math_in_text(text)
    step2 = AcademicMathFormatter.format_math_in_text(step1)
    step3 = AcademicMathFormatter.format_math_in_text(step2)
    assert step1 == step2 == step3 == text, f"Idempotency failed:\nExpected: {text}\nGot: {step2}"

def test_defensive_fallbacks():
    # 8. Defensive checks on None, empty string, non-strings
    assert AcademicMathFormatter.format_math_in_text("") == ""
    assert AcademicMathFormatter.format_math_in_text(None) == ""
    assert AcademicMathFormatter.escape_html_outside_math("") == ""
    assert AcademicMathFormatter.escape_html_outside_math(None) == ""
    assert AcademicMathFormatter.format_math_in_text(123) == ""

if __name__ == "__main__":
    test_greek_phonetics()
    test_false_positive_elimination()
    test_complex_academic_equations()
    test_html_escape_outside_math()
    test_idempotency_alignment()
    test_defensive_fallbacks()
    print("✅ All AcademicMathFormatter & Prompt alignment unit tests passed flawlessly!")
