# 저장소 감사 및 기준선 보고서 (P0)

**작성 일시**: 2026-09-10
**작업 목표**: 자소서 아카이브·RAG 검색·스타일 수정 기능 구현을 위한 저장소 식별, 기준선 측정 및 변경 격리 정책 수립.

---

## 1. 저장소 식별 및 작업 트리 상태

| 구분 | 내용 | 비고 |
|---|---|---|
| 요청 저장소 명칭 | `anti-paper` | 원격 식별 불가 (GitHub API 404) |
| 로컬 작업 경로 | `<로컬 작업 경로>` | 현재 작업공간 |
| 원격 origin | `https://github.com/4dong/Anti-paper.git` | remote 변경 금지 원칙 준수 |
| 기준 브랜치 | `main` | 최신 커밋 추적 중 |
| HEAD 커밋 | `21617450b6f07d92fc29f187778244a61053647e` | feat(key_manager): add native .env dual-sync... |

### 작업 트리 미커밋 변경 보존
기존 미커밋 변경 파일(10개) 및 미추적 파일(5개)은 삭제·stash·reset하지 않고 온전히 보존한다.

- **수정된 기존 파일**:
  - `.streamlit/config.toml`
  - `app.py`
  - `core/math_formatter.py`
  - `core/parser.py`
  - `core/qa_agent.py`
  - `core/translator.py`
  - `run.sh`
  - `ui/components.py`
  - `ui/sidebar.py`
  - `ui/styles.py`
- **기존 미추적 파일**:
  - `core/visual_highlighter.py`
  - `tests/test_google_translation_math.py`
  - `tests/test_math_formatter.py`
  - `tests/test_retranslation_cache.py`
  - `tests/test_visual_highlighter.py`

---

## 2. 런타임 환경 및 기존 테스트 기준선

### 실행 환경
- Python: `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3` (Python 3.12.x)
- 가용 라이브러리: `numpy`, `pillow`, `requests`, `pydantic`, `torch`, `scikit-learn` 등
- 미설치 의존성: `bs4` (BeautifulSoup4) 미설치로 일부 기존 학술 검색 모듈 테스트 제한

### 기존 테스트 실행 결과 (Baseline)
- `tests/test_key_manager.py`: **통과** (`✅ KeyManager tests passed.`)
- `tests/test_math_formatter.py`: **통과** (`✅ All AcademicMathFormatter & Prompt alignment unit tests passed flawlessly!`)
- `tests/test_visual_highlighter.py`: **통과** (`12 tests OK`)
- `tests/test_google_translation_math.py`: **통과** (오프라인 폴백 처리)
- `tests/test_retranslation_cache.py`: **통과** (오프라인 폴백 처리)
- `tests/test_core.py`, `tests/test_e2e.py`, `tests/test_qa_agent.py`, `tests/test_recommender.py`: `bs4` 부재로 실행 실패 (기존 상태)

---

## 3. 모델 사양 및 외부 API 가용성 (2026-09 실측)

실시간 웹 검색(`search_web`)을 통한 공식 사양 확인:
- **텍스트/비전(OCR/RAG/스타일)**:
  - `gemini-3.8-flash`: 최신 Flash 티어 모델 (코딩/에이전트/추론 최적화)
  - `gemini-2.5-flash`: 고속/저비용 멀티모달 추론
  - `gemini-2.5-pro`: 심층 추론
- **임베딩(Vector Search)**:
  - `gemini-embedding-2`: 멀티모달 & 텍스트 임베딩 (기본 3,072차원, MRL 768/1536 지원)
  - `gemini-embedding-001`: 고성능 텍스트 전용 임베딩
  - *주의*: 과거 모델인 `text-embedding-004`는 2026년 1월부로 폐기(deprecated)되었으므로 사용 금지.
- **오프라인/로컬 모드**:
  - API 키가 없거나 외부 통신 차단 시에도 SQLite FTS5 기반 키워드 검색, 수동 전사, 규칙 기반 검증, 수치 보존 검사는 100% 로컬에서 동작해야 함.

---

## 4. 데이터 보관 및 아키텍처 원칙

1. **아카이브 루트**:
   - 기본 경로: `~/EssayArchive` (환경변수 `ESSAY_ARCHIVE_ROOT`로 재지정 가능)
   - 논문 서재 `~/PaperArchive`와 물리적·논리적으로 완전 분리.
2. **저장 구조**:
   - 진실 원장(Source of Truth): SQLite 데이터베이스 (`~/EssayArchive/db/essay_archive.db`)
   - 원본 미디어: 변형 없이 `~/EssayArchive/sources/{sha256[:2]}/{sha256}.{ext}`에 저장.
   - 내보내기: 언제든 재생성 가능한 TXT/Markdown/ZIP.
3. **독립 모듈화**:
   - 기존 `core/downloader.py` (Paper/ArchiveManager)에 의존하지 않고 `core/essay/` 전용 모듈 신설.
   - UI 역시 `ui/essay/`로 격리하여 논문 기능과 충돌 방지.
