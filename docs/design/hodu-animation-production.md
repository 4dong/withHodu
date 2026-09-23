# 호두 애니메이션 이미지 제작

> 제작 원본(`frames/`, `previews/`, `source/`)은 [Release `hodu-art-v1`](https://github.com/4dong/withHodu-paper-translator/releases/tag/hodu-art-v1)로 옮겼습니다. 이 문서의 경로는 그 zip을 저장소 루트에 푼 기준입니다.

작성: 2026-09-14 · 기준: `assets/hodu/hodu-pixel-reference-v1.png`

이미지 제작 **5/5 완료** · 실제 앱 적용 **4/4 완료**

| 단계 | 작업 | 상태 |
| --- | --- | --- |
| 1/5 | 변경된 앱 코드 및 동작 연결점 확인 | 완료 |
| 2/5 | 한 시트에 한 동작, 5종의 12프레임 원화 생성 | 완료 |
| 3/5 | 로컬 배경 제거와 개별 프레임 추출 | 완료 |
| 4/5 | 정렬·타이밍·루프 검토, 재생 미리보기 | 완료 |
| 5/5 | 자산 목록과 적용 위치 문서화 | 완료 |

## 이미지별 주제와 적용 위치

| 자산 | 한 장의 주제 | 현재 코드 연결점 | 의도 |
| --- | --- | --- | --- |
| loading-walk-01 | 오른쪽을 향한 제자리 걷기, 12프레임 | `ui/hodu.py::walking_html`, `.h-walk-dog`, `.hodu-side` | 발 접지·통과·들림의 실제 변화. 화면 가로 이동은 기존 바깥 요소 담당 |
| loading-fetch-02 | 종이를 물고 걷기, 12프레임 | `app.py::process_paper_and_load`, `loading(..., pose="fetch")` | 다운로드·논문 가져오기 |
| reading-01 | 앞발로 책 한 장 넘기기, 12프레임 | `loading(..., pose="read")`, 번역·전사 | 앞발 이동, 종이가 휘는 중간 프레임, 펼친 책으로 복귀 |
| home-shake-01 | 앉아서 물기 털기, 12프레임 | `ui/home.py`의 `.hodu-hero-dog` | 잠깐 몸을 턴 후 원래 자세로 복귀, 작은 물방울 |
| home-idle-01 | 앉아서 눈 깜박이고 꼬리 흔들기, 12프레임 | `ui/home.py::home_animation_html` | 긴 휴지기를 두는 조용한 유휴 동작 |

## 제작 규칙

- 원본의 황금색 포메라니안, 크림 주둥이/가슴, 작은 귀, 둥근 검은 눈과 코, 등 위에 말린 꼬리, 갈색 도트 외곽선 유지.
- 각 시트는 4열×3행, 행 우선 순서 1→12. 하나의 주제만 포함. 라벨과 격자선은 원화에 넣지 않는다.
- 프레임의 크기와 시점은 일정하게 유지하고 전체 동작에 필요한 여백을 확보한다.
- 생성 도구에서 신뢰할 수 있는 alpha를 얻지 못했던 전력이 있어 단색 배경으로 생성한 뒤 사용자 동의가 있는 로컬 처리로 투명화한다.
- 캐릭터를 새로 그리는 작업은 image_gen, 배경 제거·자르기·정렬·미리보기 조합은 로컬 코드로 수행한다.
- 실제 주사율 60/120Hz와 고유 원화 12프레임은 별개다. 12프레임은 동작별 0.9–2초 정도로 재생하고, 가로 이동은 브라우저 합성으로 부드럽게 처리하는 방식이 적합하다. 단순 프레임 복제로 세부 동작이 증가했다고 주장하지 않는다.
- 생성된 프레임의 미세한 실루엣/크기 흔들림을 검토하고 품질 한계를 명시한다. 런타임 적용 결과는 아래 별도 검증 기록으로 남긴다.

## 산출물

- `assets/hodu/animations/source/`: 생성 원본, 프롬프트
- `assets/hodu/animations/sheets/`: 투명 프레임 시트
- `assets/hodu/animations/frames/<animation>/`: 개별 PNG (예: loading-walk-01-01.png)
- `assets/hodu/animations/previews/`: APNG/GIF 재생 미리보기
- `assets/hodu/animations/manifest.json`: 프레임 순서, 크기, 재생시간, 적용 위치
- `docs/design/previews/hodu-animations/index.html`: 모든 애니메이션을 비교하는 로컬 미리보기

앱의 최신 `walking` 오버레이 및 숨김 리더 컨트롤 변경은 유지한다. 제작한 애니메이션은 아래 후속 적용을 통해 실제 로딩과 메인 화면에 연결했다.


## 완료 기록

- 내장 image_gen 호출 5회, 원본 기준표를 캐릭터/도트 스타일 레퍼런스로 사용. 실제 프롬프트는 `assets/hodu/animations/source/*-prompt.txt`에 저장.
- 생성본 5종 모두 1448×1086 RGBA로 출력됨. 이미 투명 채널이 있어 별도 흰 배경 키잉을 하지 않고 alpha를 보존함. 16/255 미만의 잔여 alpha만 정리.
- 4×3 프레임 추출 후 368×368 캔버스, 기준점 (184, 324)에 평행 이동으로 정렬. 프레임마다 별도 확대/축소는 하지 않음.
- 완성 시트 5장(1472×1104), 서로 다른 개별 프레임 60장, APNG 5개, 번호/시간 기준표 5장.
- `assets/hodu/animations/validation.json`: RGBA, 12개 고유 프레임, 투명 여백, APNG 프레임 수 검증 통과.
- `scratch/hodu-animation-verification/report.json`: Chrome에서 5개 시트 로딩, 재생 변화, 정지, 7번 프레임 선택, 어두운 배경, 1280/390px 가로 넘침 없음 확인.
- 이미지 제작 단계에서는 기반 자산을 제공했고, 후속 요청에 따라 아래와 같이 실제 앱에 적용함.
- 후속 적용에서는 머리/털무늬의 미세한 프레임 간 변화와 루프 접합을 실제 표시 크기에서 추가 조율할 수 있음. 완벽한 수작업 인비트윈/60fps 원화로 주장하지 않음.

[재생 미리보기](previews/hodu-animations/index.html) · [자산 안내](../../assets/hodu/animations/README.md)

## 실제 앱 적용 및 검증 — 2026-09-14

| 단계 | 작업 | 상태 |
| --- | --- | --- |
| 1/4 | 최신 walking/loading/home 연결 구조 확인 | 완료 |
| 2/4 | 투명 시트와 프레임별 CSS 재생 연결 | 완료 |
| 3/4 | 브라우저 화면·동작·접근성·회귀 검증 | 완료 |
| 4/4 | 적용 기록 정리 | 완료 |

- `ui/hodu_animations.py`: manifest 기준 재생 시간과 시트 위치를 CSS 키프레임으로 생성. 필요한 시트만 로드.
- `ui/hodu.py`: 검색/페이지 전환은 걷기, 가져오기/정리는 종이 물고 걷기, 읽기/분석은 책 넘기기로 연결. 기존 임시 로딩 표시의 종료 및 예외 처리 유지.
- `ui/home.py`: 약 16초 동안 대기 동작 후 물기 털기 2.52초를 한 번 재생하는 주기를 반복.
- OS 또는 앱의 움직임 줄이기 설정에서는 정지 프레임을 표시.
- 실제 UI 모듈을 사용하는 로컬 검증 화면에서 Chrome 데스크톱 및 390px 모바일 확인: 프레임 변화, 유휴/물기 털기 전환, 투명 배경, 가로 넘침 없음, 로딩 성공/실패 후 제거, 두 움직임 감소 설정 통과. 실제 외부 논문 다운로드는 실행하지 않음.
- `tests/test_hodu_ui.py`: 11개 테스트 통과.
- 증거: `scratch/hodu-runtime-verification/report.json`, 같은 폴더의 화면 PNG, `scratch/hodu-animation-integration-tests.log`.

## 메인 대기 동작 보정 — v2

- 1/3 원인 확인, 2/3 제작·연결, 3/3 검증 완료.
- 기존 9→10번에서 머리·몸통까지 이동하던 전체 포즈 교체를 제거했다.
- `home-idle-02`: 고정 원본 몸통 뒤에 생성한 꼬리 중간 자세를 합성. 22개 왕복 재생 구간과 5개 눈 깜박임/휴지 구간, 총 27프레임. 재생 프레임 수는 고유 생성 원화 수와 다르다.
- 눈 주변을 제외한 불투명 몸통 픽셀은 전 프레임 동일함을 코드로 검증한다. 원본 v1은 보관하며 메인은 v2를 사용한다.
- 재현 스크립트: `scripts/refine_hodu_idle.py`. 투명 시트: `assets/hodu/animations/sheets/home-idle-02.png`.
- 내장 image_gen으로 꼬리 전용 12자세를 생성하고 로컬 추출·합성했다. 프롬프트 요지: 원본 황금색 도트 털을 유지한 투명 4×3 꼬리 전용 시트, 고정된 뿌리, 왼쪽 기울임→중앙→오른쪽 기울임의 세밀한 중간 자세, 몸·얼굴·모션선 제외.
- 검증 결과: 현재 UI 테스트 7개 통과, Chrome에서 v2 시트 로드 및 모바일 가로 넘침 없음, OS/앱 움직임 감소 및 로딩 정리 확인. `scratch/hodu-runtime-verification/report.json`, `scratch/hodu-idle-v2-tests.log` 참조.

### 대기→물기 털기 표시 크기 보정

두 원화는 동일한 368px 캔버스지만 물기 털기 캐릭터 높이가 약 6% 작았다. `ui/hodu.css`에서 발 접지점(높이 88.043478%)을 기준으로 물기 털기 레이어만 1.062배, 가로 -2.99% 보정했다. 원본 이미지와 프레임 재생은 유지한다. Chrome 데스크톱/모바일 전환 화면 및 움직임 감소 동작 확인.

### 꼬리 질감 복원 및 물기 털기 완충

- 내장 image_gen으로 `source/home-idle-tail-v3.png`의 털 도트 질감을 보강했다. `refine_hodu_idle.py`가 이 원화를 사용하며 몸통 불투명 픽셀 고정 검사를 통과했다.
- `source/home-shake-inbetweens.png`에서 11개 추가 자세를 추출하여 기존 12장 사이에 삽입했다. 새로운 `home-shake-02`는 23프레임, 총 4230ms이며 주요 동작의 유지 시간은 130ms다. 원본 12장은 보관한다.
- 재현: `python3 scripts/refine_hodu_idle.py`, `python3 scripts/refine_hodu_shake.py`. 생성 프롬프트는 각 source 이미지 옆의 `-prompt.txt`에 저장했다.
- 실제 앱은 `home-shake-02` 사용. Chrome 데스크톱/390px 모바일, 움직임 감소, 오류 없음 확인. UI 테스트 7개 통과 (`scratch/hodu-cushion-tests.log`).

### 사용자 확대 이미지 기준 꼬리 형태 재수정

오른쪽 꼬리의 긴 깃털형 무늬를 제거하고 짧은 사각 도트 털뭉치와 불규칙한 외곽으로 변경했다. 첫 v4 시도는 긴 무늬가 남아 채택하지 않았다. 내장 image_gen으로 만든 v5를 최종 채택하고 `refine_hodu_idle.py`의 원본 참조를 바꿨다. 축소 시 도트 유지(NEAREST), 몸통 불투명 픽셀 동일성 검사 통과. 물기 털기 자산·타이밍은 변경하지 않았다. 최종 프롬프트: `assets/hodu/animations/source/home-idle-tail-v5-prompt.txt`. 최종 앱 시트: `assets/hodu/animations/sheets/home-idle-02.png`.

### 오른쪽 볼·옆구리 털 경계 복구

사용자 확대 이미지에서 문제 부위를 다시 확인했다. 꼬리 질감뿐 아니라 기존 몸통 분리 다각형 마스크가 오른쪽 볼·옆구리의 도트 외곽을 직선으로 잘라내고 있었다. 해당 다각형을 제거하고 왼쪽 원본의 실제 털끝 픽셀을 오른쪽 외곽 27px 띠에 대칭 복원했다. 안쪽 얼굴·눈·주둥이·가슴은 유지하고, 꼬리는 복구한 몸통 뒤에 합성한다. 전 대기 프레임의 불투명 몸통 픽셀 동일성 검사 통과. 확대 확인: `scratch/hodu-right-fur-fixed.png`. 물기 털기는 변경하지 않았다.

### 꼬리 방향 전환 완충 3장 추가

내장 image_gen으로 `source/home-idle-tail-cushion.png`의 중간 자세 3장을 생성했다. 중앙→오른쪽 구간에 삽입하고 복귀 시 역순으로 재사용한다. 각 완충 자세는 80ms, 기존 자세는 110ms이며 대기 시트는 27→33 재생 프레임(6열×6행)으로 갱신했다. 복구한 볼·옆구리 포함 몸통 픽셀 고정 검사 및 UI 테스트 7개 통과. 물기 털기 변경 없음. 프롬프트는 원본 옆 `home-idle-tail-cushion-prompt.txt`에 저장.
