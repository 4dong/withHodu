# 호두랑 UI 정교화 검증

2026-09-14 · 관련 설계: [설계 노트](withhodu-ui-refinement-plan.md)

## 반영한 내용

- `assets/hodu/hodu-pixel-transparent-v1.png`: 원본 RGB 값을 바꾸지 않은 RGBA 아틀라스. 원본 파일은 보존.
- `scripts/prepare_hodu_transparency.py`: 사용자 동의에 따라 로컬에서 배경 연결 영역만 제거하는 재현 가능한 스크립트.
- `ui/hodu.py`: 투명 자산 연결, 수정시간 기반 이미지 캐시, 메뉴 이동 시 스크롤 초기화.
- `ui/hodu.css`: 공통 토큰과 48px 버튼·입력, 상태와 포커스, 54px 내비게이션, 표면과 타이포그래피, 실제 React Aria DOM 지원.
- `ui/home.css`, `ui/home.py`: 3가지 주요 기능의 카드와 52px CTA, 반응형 크기·간격·정렬, 모바일 상단 잘림 수정.
- `ui/sidebar.py`: 주요 메뉴 우선 배치, 홈 링크의 비중 축소, 움직임 설정을 화면 설정 안으로 이동.
- `ui/library_view.py`: 전체 폭 헤더와 요약 도구 행, 카드 내부 보고서 버튼, 컬렉션 제목과 삭제 액션 한 줄 배치.
- `app.py`: UI 모듈 재로딩과 검색 CTA, `.streamlit/config.toml`: 새 팔레트 기본값.

## Ran — 실행한 검증

| 검증 | 결과 | 증거 |
| --- | --- | --- |
| 원본·투명 아틀라스 픽셀 비교 | 1448×1086 RGBA, RGB 채널 완전 일치, 배경 899,948픽셀 투명화, 주요 전경 좌표 불투명 유지 | `assets/hodu/hodu-transparency-report.json` |
| Chrome CDP: 홈·서재·검색·자소서, 사이드바 | 1280×900 / 390×844, 런타임 오류 없음, 가로 넘침 없음 | `scratch/ui-refinement-verification/report.json` |
| 버튼 실측 | 홈 CTA 52px, 사이드바 메뉴 54px | 같은 report.json |
| 클릭 직후 재실행 상태 | 검증용 callback에 1.2초 지연을 주어 18개 stale 요소 상태에서 캡처. 전·중·후 모든 호두 이미지의 PNG color type=6, filter=none, blend=normal | `interaction-report.json`, `library-during-rerun.png`, `library-after-rerun.png` |
| 입력창/키보드 | 입력 루트 48px, 포커스 테두리·링 확인. Tab으로 검색 버튼 도달, solid outline | `interaction-report.json`, `search-keyboard-focus.png` |
| 호버·눌림 | 실제 CDP 포인터 입력으로 캡처 | `library-button-hover.png`, `library-button-pressed.png` |
| 12개 컬렉션 | 임시 저장소에 검증 전용 빈 컬렉션 생성. 데스크톱/모바일 각각 카드 크기 동일, 모든 보이는 버튼이 카드 내부. 검증 후 빈 폴더 삭제 | `extended-report.json`, `collections-12-desktop.png`, `collections-12-mobile.png` |
| 리더·호두 8개 포즈·상태 | 별도 로컬 UI 자료로 렌더링. 밝은/어두운 배경, empty/success/error/loading, 가로 넘침/런타임 오류 없음 | `extended-report.json`, `reader-desktop.png`, `reader-mobile.png`, `states-desktop.png` |
| 움직임 감소 | prefers-reduced-motion에서 호두 animation-name=none | `extended-report.json` |
| `python3 -m unittest tests.test_hodu_home tests.test_hodu_ui` | 7개 테스트 통과 | `scratch/ui-refinement-verification/apptest.log` |
| Python 문법·변경 공백 | compileall 및 git diff --check 통과 | 로컬 실행 결과 |

위 표의 파일명이 단독인 경로는 모두 `scratch/ui-refinement-verification/` 아래에 있다.

## Manual — 캡처를 보고 확인

- 흰 사각형 배경 없이 원본 색의 호두가 시작 화면·사이드바·페이지 헤더에 표시된다.
- 서재 진입 버튼을 누르는 재실행 상태에서도 흰 배경이 다시 나타나지 않는다.
- 호두의 털·책·종이·원본 그림자 영역은 남아 있다. 이 밝은 전경 부분은 배경 제거 대상이 아니다.
- 홈의 세 CTA가 동일한 기준선과 높이에 정렬되고, 모바일에서 상단 브랜드와 제목이 가려지지 않는다.
- 컬렉션 삭제 액션은 좁은 카드에서도 줄바꿈되지 않고 제목 옆에 유지된다.

## 검증 범위의 한계

- 외부 논문 검색·유료 번역·실제 문서 업로드와 삭제는 실행하지 않았다. 이번 변경은 UI 표시이며 실제 데이터나 키를 사용할 필요가 없다.
- 리더 렌더링은 `scratch/reader_fixture.py`의 명시적인 UI 검증 자료를 사용했다. 실제 PDF 번역 품질의 검증으로 해석하지 않는다.
- Safari·Firefox와 스크린리더 전체 감사는 수행하지 않았다. 실제 브라우저 검증은 로컬 Chrome이다.
- 상태 키워드 검사 도구는 Python/Streamlit 실행 화면의 대체 증거로 사용하지 않았다.

## 인수 검수 (Claude, 2026-09-14)

Codex가 이 노트를 쓰던 중 사용량 한도로 멈췄다. 이 절은 기록된 결과를 다시 확인하고 부족한 부분을 보완한 내용이다. 새로 만든 증거는 `scratch/ui-refinement-verification/claude-review/`에 있다.

### 기록에서 바로잡은 점

- `library-mobile.png`와 `sidebar-mobile.png`는 해시가 같은 파일이다. 사이드바가 본문을 덮은 화면이라 서재 모바일 본문의 증거가 되지 못한다. `library-desktop.png`, `sidebar-desktop.png`, `library-after-rerun.png` 세 파일도 해시가 같다. 서재 모바일 본문은 `claude-review/library-cards-mobile.png`로 새로 확인했다.
- "12개 컬렉션 카드 크기 동일"은 이름 길이가 모두 같은 검증 데이터에서만 성립했다. 긴 이름이 섞이면 카드가 305px와 221px로 달라졌다(아래 결함 3).
- `check_ui_extended.mjs`는 크기가 0인 버튼을 판정에서 뺀다. 카드마다 보이지 않는 버튼이 하나씩 있어 이 필터는 타당하다. 필터 없이 따로 측정해서도 확인했다.
- 홈 CTA 52px는 데스크톱에서만 성립한다. 모바일에서는 `[data-testid="stMain"] button[kind]` 규칙의 명시도가 더 높아 48px가 된다. 설계값(52px)과 다르지만 44px 이상이라 조작에는 문제가 없어 그대로 두었다. tertiary 버튼의 40px 규칙도 기본 48px 규칙에 밀려 적용되지 않는다.

### 발견해 수정한 결함

| # | 결함 | 원인 | 수정 |
| --- | --- | --- | --- |
| 1 | `think` 포즈는 머리 오른쪽 14px, `rest`는 꼬리 16px, `organize`는 5px가 잘림. `think`는 오류·빈 상태 화면에 쓰임 | 스프라이트 좌표가 실제 그림 경계와 어긋남 | 투명 아틀라스의 alpha 경계로 좌표 재측정. think `-194px`, organize `-187px`, rest 너비 `192px`. 넓은 rest는 틀마다 배율을 낮춤 (`ui/hodu.css`) |
| 2 | 사이드바와 본문의 expander 테두리가 두 겹(곡률 16px + 8px) | wrapper와 Streamlit의 details 요소가 각각 테두리를 그림. 09-11 CSS부터 있던 문제 | details 테두리를 없애고 wrapper 테두리만 남김 |
| 3 | 긴 컬렉션 이름이 5줄로 줄바꿈되어 같은 줄 카드의 높이가 달라짐 | 삭제 버튼 열을 74px로 고정하면서 제목 열이 좁아짐 | 제목을 2줄로 제한하고 넘치면 말줄임. 전체 이름은 `title` 툴팁으로 표시 (`ui/library_view.py`, `ui/hodu.css`) |
| 4 | 사이드바에서 "작업 설정" 바로 아래에 "번역 설정"이 이어짐 | 6/6에서 추가한 라벨이 각 작업 영역의 기존 제목과 겹침 | "작업 설정" 라벨 제거 (`ui/sidebar.py`) |
| 5 | (수정 중 생긴 회귀) 호두 이미지와 공통 테마가 통째로 사라짐 | CSS 주석에 쓴 태그 모양 문자열 때문에 `st.html`의 정리 과정이 `<style>` 전체를 삭제 | 주석 수정. CSS 파일에 태그 모양 문자열이 있으면 실패하는 `ThemeCssTests` 추가 (`tests/test_hodu_ui.py`) |

5번은 수정 후 재검증에서 호두 초상 크기 0, expander 테두리 0px로 드러났다. 추가한 테스트의 정규식이 원래 주석 문자열을 잡아내는 것도 확인했다.

### 재검증 결과 (수정 후)

| 검증 | 결과 | 증거 |
| --- | --- | --- |
| Chrome CDP: 홈·서재·검색·자소서·상태, 1280×900 / 390×844 | 가로 넘침 0, Streamlit 예외 0, 콘솔 오류 0 | `claude-review/final-report.json`과 화면별 PNG |
| 호두 초상 잘림 | 8개 포즈 모두 틀 안에 들어옴. 모바일 헤더의 read·search만 1.6px 넘치지만 투명 여백(약 2.4px) 안이라 그림은 잘리지 않음 | `final-report.json`, `states-*.png` |
| 재실행 중 흰 사각형 (픽셀 판정) | 스프라이트 사각형 안쪽 테두리의 78–89%가 바깥 배경색과 같음. 흰색이 아닌 #F7F8FA·#EEF4EF 배경 위에서도 같아 배경이 투명함을 확인. stale 요소 18개 상태 포함 | `rerun-before/during/after.png` |
| 긴 컬렉션 이름 | 데스크톱·모바일 모든 카드 221px, 제목 2줄, title 속성 있음, 버튼이 카드 안에 있음 | `library-cards-*.png` |
| Expander | wrapper 1px·곡률 16px, details 0px, 펼친 상태 구분선 #E4EAE6 | `sidebar-expander-open-desktop.png` |
| 기존 회귀 스크립트 재실행 | `check_ui_refinement.mjs`, `check_ui_interactions.mjs` 오류 0. PNG color type 6, filter none, 입력 48px, 키보드 포커스 solid. 수정 후 코드로 `report.json`, `interaction-report.json`과 해당 PNG를 새로 만듦 | 이 폴더의 `report.json`, `interaction-report.json` |
| 단위 테스트 | `tests.test_hodu_home`, `tests.test_hodu_ui` 8개 통과(1개 추가). `test_math_formatter`, `test_visual_highlighter` 12개 통과 | 로컬 실행 |
| 자소서 테스트 | pytest가 pyenv와 `.venv` 어디에도 없어, 네트워크를 막고 저장된 키 조회를 비운 상태에서 테스트 함수 24개를 직접 호출해 모두 통과 | 로컬 실행 |

검증용 컬렉션 3개(긴 이름 포함)는 `scratch/ui-refinement-data/papers`에만 만들었고, 검증 후 삭제했다. `extended-report.json`(12개 컬렉션, 리더)은 Codex가 수정 전에 실행한 결과 그대로다.

### 실행하지 않은 것과 후속 후보

- 실행하지 않은 테스트: `test_e2e`, `test_core`, `test_google_translation_math`, `test_key_manager`, `test_recommender`, `test_retranslation_cache`, `test_qa_agent`. 외부 네트워크나 저장된 키, 실제 LLM을 쓴다.
- 호두 아틀라스(약 1.7MB)를 base64로 바꿔 재실행마다 `st.html`로 보낸다(원본 PNG를 쓰던 때부터의 방식). 정적 파일로 제공하거나 포즈별로 잘라 보내면 전송량을 줄일 수 있다.
- `app.py`의 검색·논문 열기 오류 처리는 `except Exception`에서 로그 없이 안내 문구만 보여 준다. Streamlit의 rerun 제어 예외는 `BaseException` 계열이라 이동은 막히지 않지만, 실패 원인을 추적하려면 로그를 남기는 편이 낫다.
- 자소서 사이드바에 로컬 절대 경로가 그대로 표시된다(이전부터 있던 동작).
