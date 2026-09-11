# 자소서 아카이브 & RAG 시스템 모듈 안내

## 1. 모듈 구성 및 아키텍처

- **데이터 계층 (`core/essay/`)**:
  - `models.py`: Document, Answer, Revision, Chunk, Embedding, Tag, Job 등 Typed DTO 정의.
  - `repository.py`: SQLite WAL 기반 트랜잭션, `schema_migrations` 관리, 원본 SHA-256 중복 제거 저장, 소프트 삭제(Tombstone), TXT/MD/ZIP 내보내기, `seed.json` 멱등적 가져오기.
  - `ingest.py`: 이미지(JPG/PNG/WEBP) 무결성 검증, 50MB 용량/100페이지 한도 검사, TXT/MD 직접 전사.
  - `transcription.py`: `GeminiVisionOCRProvider` (Gemini 2.5 Flash / 3.8 Flash) 및 오프라인/테스트용 `MockOCRProvider`.
  - `jobs.py`: SQLite 기반 단일 로컬 워커 작업 큐, 원자적 리스(Lease) 획득, 최대 3회 백오프 재시도.
  - `tagging.py`: 10개 패싯(기업, 직무, 기술 등) 사전, 별칭(파이토치->PyTorch 등) 매핑, 본문 정규식 근거 추출.
  - `chunking.py`: 본문 `[start_char, end_char)` 오프셋 보존 문항/경험 단위 청커.
  - `embedding.py`: `GeminiEmbeddingProvider` (`gemini-embedding-001`, `gemini-embedding-2`) 및 단위 벡터 검증 `MockEmbeddingProvider`.
  - `retrieval.py`: SQLite FTS5 trigram 전문 검색 + NumPy 정확 코사인 벡터 검색 + RRF(Reciprocal Rank Fusion) 하이브리드 검색기.
  - `rag.py`: 인용 검증기(Substring 대조), 프롬프트 주입 방어, 한계점/근거부족 분기 처리 RAG 서비스.
  - `style.py`: 사실 원장(`FactLedger`), 스타일 프리셋 및 벤치마킹 문체 추출, 수치 보존/금지어 검증, 낙관적 락 기반 리비전 채택.
  - `backup.py`: SQLite 온라인 백업 및 원본 소스 파일 압축 ZIP 백업/복원 엔진.

- **사용자 인터페이스 (`ui/essay/`)**:
  - `workspace.py`: 상위 작업공간 라우터 및 탭 네비게이션.
  - `library_view.py`: 자소서 카드 탐색, 필터링, 문항 열람, MD/TXT/ZIP 내보내기 및 삭제.
  - `import_view.py`: 일괄 사진/문서 업로드, 묶음 지정 및 전사 큐 등록.
  - `review_view.py`: 좌측 원본 사진 대조 + 우측 텍스트 편집기, 불명확 단어 안내, 검수 승인 및 색인.
  - `search_view.py`: 하이브리드 검색, 근거 인용 AI 답변, 출처 원문 카드 표시.
  - `style_view.py`: 초안 선택, 문체 프리셋, 사실 보존 리포트, 수정본 채택/새 버전 생성.

## 2. 실행 및 검증 명령어

### 앱 실행
```bash
./run.sh
# 또는
python3 -m streamlit run app.py --server.port=8501
```

### 테스트 전체 실행
```bash
# 자소서 전용 테스트 스위트
python3 tests/essay/test_repository.py
python3 tests/essay/test_ingest_ocr.py
python3 tests/essay/test_tag_search.py
python3 tests/essay/test_rag.py
python3 tests/essay/test_style.py
python3 tests/essay/test_backup_lifecycle.py

# 기존 Scholar 테스트 스위트 병행 검증
python3 tests/test_key_manager.py
python3 tests/test_math_formatter.py
python3 tests/test_visual_highlighter.py
python3 tests/test_google_translation_math.py
python3 tests/test_retranslation_cache.py
```
