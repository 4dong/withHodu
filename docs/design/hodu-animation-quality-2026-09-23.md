# 호두 애니메이션 품질 개선

## 확인한 문제

- 같은 368×368 캔버스지만 대기 강아지 실루엣은 274×294px, 기존 몸 털기 시작은 246×277px, 끝은 253×274px였다(전체 alpha bbox 기준).
- 자동 몸 털기에만 CSS 1.062배 확대가 적용되고, 클릭으로 호출한 몸 털기에는 적용되지 않았다.
- 기존 몸 털기는 입을 벌린 얼굴, 다른 머리 윤곽/꼬리 모양으로 대기 호두와 정체성이 달랐다.
- 대기와 몸 털기 시계가 따로 돌아서 복귀 시 대기 애니메이션의 임의 프레임이 나타났다.

## 적용

- 기준은 기존 `home-idle-02` 첫 프레임. 원본 보존.
- built-in image_gen으로 기준 이미지를 참조한 몸 털기 `home-shake-03`와 손 쓰다듬기 `home-pet-01` 생성.
- 몸 털기 초안의 꼬리가 반대편으로 바뀐 프레임은 생성 도구로 수정. 쓰다듬기 초안의 손 방향이 바뀐 프레임은 제외.
- 시트별 동일 배율, nearest-neighbor 리사이즈, 발바닥 y=324 정렬. 동작 시작·끝은 생성 이미지 대신 기존 대기 프레임을 그대로 넣어 픽셀 일치 보장.
- 몸 털기 10프레임/1670ms, 쓰다듬기 10프레임/2000ms. 손 접촉→눈 감기→좌우 부비기→손 떼기→정면 순서.
- CSS 자동 몸 털기 루프 제거. 단일 JS 제어기가 16초 대기 후 몸 털기를 재생하고, 완료 후 대기 시트를 첫 프레임부터 재생.
- 재생 시간은 manifest에서 계산. 줄인 움직임 설정에서는 정적 이미지와 문구 유지.
- 호두 위 클릭 발자국을 제외해 생성된 손/얼굴이 가려지지 않게 했다.

## 근거

- Ran: `python3 scripts/build_hodu_home_quality.py`. 원본·프레임·시트·APNG·콘택트 시트 생성.
- Ran: `python3 -m unittest tests.test_hodu_emotions tests.test_hodu_ui.ThemeCssTests` — 5개 통과. 시작/끝 픽셀 동일성과 manifest 재생 시간 확인.
- Ran: `node scratch/check_hodu_touch.mjs` — 로컬 Chrome 1280×900 / 모바일 터치 에뮬레이션 390×844. 클릭·터치·키보드·반복 입력·줄인 움직임·몸 털기 후 대기 시계 재시작과 16초 자동 재생·복귀 확인. 결과: `scratch/hodu-quality/browser/report.json`.
- Ran: alpha bbox 전후 측정: `scratch/hodu-quality/before-bounds.json`, `scratch/hodu-quality/after-metrics.json`. 새 두 동작의 20개 프레임 모두 발 기준 y=324.
- Manual: 원본, 새 콘택트 시트, 데스크톱 쓰다듬기/모바일 화면 확인. 생성 중간 자세에는 의도된 고개·털 윤곽 변화가 있으며 완전한 몸통 픽셀 고정은 아니다.
- Skipped: alignment-validator의 OpenCV 기반 스크립트는 opencv-python 부재로 실행 불가. 투명 배경의 alpha bounds와 endpoint byte 비교로 직접 검증했다. 실제 모바일 기기 검증은 미실행.

## 산출물

- `assets/hodu/animations/previews/home-pet-01.apng`
- `assets/hodu/animations/previews/home-shake-03.apng`
- 프롬프트: `assets/hodu/animations/source/home-pet-01-prompt.txt`, `home-shake-03-prompt.txt`
- 재현 패키징: `scripts/build_hodu_home_quality.py`

## 사용자 피드백 반영: 원래 물 털기 복원

작은 새 몸 흔들기보다 기존의 역동적인 물 털기를 선호한다는 피드백에 따라 런타임 shake를 `home-shake-02`(23프레임, 4230ms)로 복원했다. 물방울과 고개를 크게 터는 기존 그림을 보존한다. 클릭과 자동 재생 모두 동일한 1.062배 확대/발 기준 배치를 적용한다. 처음 8%, 마지막 14% 구간에서 정면 대기 이미지와 교차 전환하며, 그동안 대기 시트는 첫 프레임에 고정된다. 전환 완료 후 대기 시계를 재시작한다. 원래 그림의 얼굴 차이는 남으며, 이를 없애기 위해 사용자가 좋아하는 동작을 다시 대체하지 않는다. 새 쓰다듬기는 유지한다.

## 후속 수정: 흰색으로 뜨는 전환 제거

두 스프라이트를 동시에 낮은 opacity로 겹치면 합성 알파가 낮아져 밝은 배경이 비쳤다. 해당 교차 전환 CSS와 대기 레이어 동시 표시를 제거했다. built-in image_gen으로 준비 4장·복귀 4장을 추가 생성했다. `home-shake-04`는 대기 원본→준비 4장→기존 물 털기 23장→복귀 4장→대기 원본의 33프레임/4390ms 시트다. 기존 물방울과 크게 터는 동작은 모두 보존한다. 화면에는 매 순간 한 시트만 opacity 1로 나타난다.

- 재현: `python3 scripts/build_hodu_shake_bridge.py`
- 원본/프롬프트: `assets/hodu/animations/source/home-shake-bridge-01.png`, `home-shake-bridge-01-prompt.txt`
- 결과: `assets/hodu/animations/previews/home-shake-04.apng`
- Ran: 6개 단위 테스트 통과. 기존 23프레임이 동일한 배율·위치 변환만 거쳐 그대로 포함되어 있는지 픽셀 비교. 새 시작/끝이 실제 대기 이미지와 동일한지 확인.
- 생성 그림의 미세한 얼굴/털 윤곽 차이는 있을 수 있다. 중간 자세를 통해 연결하며, 밝기/알파를 낮추어 감추지 않는다.

- Ran: 로컬 Chrome 클릭·터치·키보드·자동 재생/복귀 통과. 준비 구간 3개 시점에서 action opacity=1, 대기 hidden=true, 활성 시트=home-shake-04 확인. 화면 캡처 수동 확인.

## 최종 기준 변경: 물 털기 원화를 단일 레퍼런스로

사용자가 물 털기의 밝은 색감, 슬림한 비율, 얇은 윤곽선을 최선의 레퍼런스로 지정했다. 기본 호두·쓰다듬기·이전 연결 이미지의 넓은 실루엣을 기준으로 삼던 방식을 폐기했다.

- 기본 `home-idle-03`: 원래 물 털기 시작 프레임을 그대로 기본 자세로 사용. 같은 그림에서 생성한 눈 깜빡임 연결.
- 쓰다듬기 `home-pet-02`: 물 털기 정면 단 한 장을 참조해 기본 동작과 함께 생성. 고정 배율/발 기준으로 패키징하고, 진한 색 필터나 굵은 테두리 효과를 추가하지 않음.
- 물 털기 `home-shake-05`: 원래 23개 프레임 전체 보존. 마지막에 새 기본과 같은 눈 깜빡임을 연결. 양 끝은 기본 이미지와 픽셀 동일.
- 이전에 만든 둥근 준비/복귀 이미지와 기본/쓰다듬기 시트는 원본 기록으로 보존하되 런타임에서는 사용하지 않음.

### 비교와 검증

- 비교 영역: 손·눈을 피한 몸통 y=200..309. 폭은 꼬리가 포함된 하단 실루엣 y=220..289의 행별 중앙값. 특정 대표 프레임의 보조 지표이며 해부학적 몸통 치수나 전체 애니메이션의 완전 일치를 뜻하지 않는다.
- 물 털기 기준: 폭 249px, 평균 휘도 185.0/255.
- 기존 쓰다듬기: 폭 260.5px, 평균 휘도 176.0/255.
- 새 쓰다듬기: 폭 251px, 평균 휘도 181.5/255. 기본 자세는 물 털기 원본과 동일.
- Manual: `scratch/hodu-unified/comparison.png`와 새 콘택트 시트에서 색·실루엣·외곽선 비교. 생성된 세부 털 픽셀에는 작은 차이가 남는다.
- Ran: 단위 테스트 6개 통과. 현재 활성 기본/쓰다듬기/물 털기의 끝점 동일성 및 원래 물 털기 23개 프레임 보존 확인.
- 원본/프롬프트: `assets/hodu/animations/source/home-unified-01.png`, `home-unified-01-prompt.txt`. built-in image_gen 사용.
- 재현: `python3 scripts/build_hodu_unified.py`.
- 미리보기: `assets/hodu/animations/previews/home-idle-03.apng`, `home-pet-02.apng`, `home-shake-05.apng`.

- Ran: 현재 활성 시트로 Chrome 데스크톱/모바일 터치·키보드·대기 복귀·자동 물 털기 통과. 기본/쓰다듬기 화면 캡처 확인. 결과 `scratch/hodu-quality/browser/report.json`. 실제 모바일 기기 검증은 하지 않았다.
