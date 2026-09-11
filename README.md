# 🛰️ Antigravity Scholar (학술 논문 스마트 검색 & 대역 리더)

> 구글 학술 검색(Google Scholar), arXiv, Semantic Scholar, OpenAlex를 연동하여 원하는 학술 논문을 지능적으로 탐색·검증하고, 로컬 폴더에 아카이빙한 뒤 **'3분 핵심 요약'**과 **'문라이트 스타일 원문-한글 대역(Split) 리더'**를 제공하는 모듈입니다.

---

## ✨ 핵심 기능

1. **🧠 지능형 학술 검색 & 쿼리 확장**
   - 한국어/일상어 입력 시 학술용 영어 키워드 및 동의어로 자동 확장 탐색.
   - arXiv, Semantic Scholar, OpenAlex 다중 소스 실시간 연동.

2. **🛡️ 다차원 논문 신뢰도 & 적합성 검증**
   - 피인용수(Citations), 발행 연도, 게재 저널/학회 수준 분석.
   - 0~100점 적합도 점수 및 "왜 이 논문이 적합한지" 3줄 팩트체크 리포트 제공.

3. **📁 로컬 자동 아카이빙 & 내 서재 탐색**
   - 오픈액세스(Open Access) PDF 자동 다운로드.
   - `~/PaperArchive/[주제명]/[연도_논문제목]/` 구조로 체계적 저장 (PDF + 메타데이터 + 번역본).
   - 저장된 논문을 언제든 다시 열어볼 수 있는 '내 서재' 브라우징 지원.

4. **📖 문라이트 스타일 원문-한글 대역 리더 (Bilingual Split View)**
   - PyMuPDF 기반 섹션/문단 정밀 파싱.
   - 좌측 영문 원문과 우측 한글 번역이 문단별 1:1로 매핑되는 대조 리딩 뷰.

5. **⚡️ 3분 핵심 요약 & 학술 용어사전 (Glossary)**
   - 연구 목적, 핵심 가설, 방법론, 주요 결과, 의의/한계점 5대 핵심 요약.
   - 논문에 등장하는 주요 전문 용어 및 쉬운 한글 해설 제공.

6. **💬 논문과 실시간 대화하기 (Chat with Paper)**
   - 논문 본문을 기반으로 궁금한 점을 질의응답하는 전용 Q&A 챗봇.

7. **📤 다양한 형식 내보내기**
   - Notion 호환 마크다운(.md) 및 전체 데이터 JSON 다운로드 지원.

---

## 🚀 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. Streamlit 앱 실행
./run.sh
# 또는
streamlit run app.py
```

### 선택 설정 (`.env` 또는 환경변수)

| 이름 | 용도 |
| --- | --- |
| `GEMINI_API_KEY` | Gemini 번역·질문·자기소개서 기능. 없으면 Google 기본 번역과 오프라인 모드로 동작 |
| `ESSAY_ARCHIVE_ROOT` | 자기소개서 보관 위치 (기본값 `~/EssayArchive`, 환경변수로만 지정) |
| `ESSAY_SEED_DIR` | 비공개 샘플·평가 자료 폴더(`data/seed.json`, `data/evaluation.json`). 없으면 관련 테스트는 건너뜀 |

논문은 `~/PaperArchive`, 자기소개서는 `~/EssayArchive`에 저장되며 저장소에는 올라가지 않습니다.

---

## 📂 프로젝트 구조

```
Anti-paper/
├── app.py                 # 메인 Streamlit 진입점
├── requirements.txt       # 의존성 패키지 목록
├── run.sh                 # 원클릭 실행 스크립트
├── GEMINI.md              # 프로젝트 원칙 및 UI/UX 지침
├── README.md              # 프로젝트 개요 및 가이드
├── core/                  # 검색, 파싱, 번역, 검증, Q&A 핵심 모듈
├── ui/                    # 컴포넌트, 서재 뷰, 스타일 및 사이드바
├── tests/                 # 단위 / 통합 / E2E 테스트 스위트
└── docs/                  # 디자인 가이드 및 프로젝트 문서
    └── apple_design.md    # 애플 UI/UX 디자인 가이드
```

브라우저에서 `http://localhost:8501`로 접속하여 바로 사용할 수 있습니다!
