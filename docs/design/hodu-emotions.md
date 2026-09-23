# 메인 화면 호두 상호작용

구현: `ui/hodu_emotions.py`, `ui/hodu_emotions.js`, `ui/home.css`.

- idle: 물 털기 정면 이미지를 기준으로 한 새 대기·눈 깜빡임 동작. 입력이 없으면 16초 뒤 몸 털기 후 첫 프레임부터 복귀.
- curious: 마우스 접근 시 커서 방향으로 최대 7px 이동, 3도 기울임.
- happy: 호버 또는 키보드 포커스 상태. 추가 몸통 바운스 없이 대기 그림 유지.
- love: 머리 클릭·터치 시 물 털기와 색·비율·윤곽을 맞춘 손 쓰다듬기 2000ms 시트(home-pet-02) 재생.
- tickle: 배 클릭·터치 시 좌우로 간지럼 반응과 음표, 1400ms 후 복귀.
- shake: 꼬리 클릭·터치 시 기존 물방울이 튀는 큰 몸 털기 23프레임에 같은 호두의 마무리 눈 깜빡임을 연결(home-shake-05). 4810ms, 한 장씩 불투명 재생.
- 각 부위는 독립된 네이티브 버튼으로 키보드 접근 가능. 추가 입력은 즉시 새 반응으로 전환하며 같은 부위도 다시 재생.
- 머리 단독 추적은 머리/몸 분리 아트가 필요하므로 보류. 기존 몸 전체의 약한 마우스 추적 유지.
- 움직임 줄이기: 앱 설정과 OS 설정을 따르며 이동 없이 상태 문구와 하트·음표로 응답.
- 화면 이탈, 스크롤, 창 포커스 상실 시 초기화. 재설치 시 이벤트·타이머·관찰자 정리.

## 프레임 확장

1. 기존 `assets/hodu/animations/manifest.json` 규격으로 시트와 프레임 시간을 등록한다.
2. `ui/hodu_emotions.py`의 `EMOTIONS`에서 해당 상태의 `animation`을 등록한 ID로 지정한다.
3. 상태별 시트는 기존 홈 그림과 같은 300×300 CSS 영역 및 발 위치를 기준으로 맞춘다.
4. 반복 여부/프레임 시간은 manifest, 클릭 반응 유지 시간은 `EMOTIONS`의 각 `durationMs`에서 관리한다.

전용 시트는 활성 상태에서만 표시한다. 미등록 ID는 기존 홈 그림으로 대체한다. 입력 제어 로직을 수정할 필요가 없다. 현재의 몸 전체 변형 동작은 CSS에 있으며 전용 프레임 도입 시 해당 상태의 CSS 동작 강도를 함께 조정할 수 있다.

## 검증 (2026-09-23)

- Ran: `node scratch/check_hodu_touch.mjs` — 로컬 Chrome, 데스크톱 1280×900 / 모바일 390×844. 세 부위 클릭·터치, 재입력 전환·만료, Enter 활성화, OS 움직임 줄이기 확인.
- Ran: 스크린샷 수동 확인. `scratch/hodu-touch-verification/{desktop,head,belly,tail,mobile,reduced}.png`; 기계 결과 `scratch/hodu-touch-verification/report.json`.
- Ran: 모바일 가로 넘침 없음, 터치 영역 최소 56×70 CSS px.
- Ran: `python3 -m unittest tests.test_hodu_emotions tests.test_hodu_home` — 7개 중 6개 통과, 사이드바 전환 1개 타임아웃. 해당 테스트 단독 재실행 통과.
- Ran: `node --check ui/hodu_emotions.js`, `git diff --check` 통과.
- Skipped: 범용 상태·스모크 스크립트는 이 스프라이트의 터치 반응을 검사하지 않아 위 전용 브라우저 검증으로 대체. 실제 모바일 기기 검증은 미실행(Chrome 터치 에뮬레이션 사용).

최신 이미지 품질 및 전환 검증: [2026-09-23 품질 보고서](hodu-animation-quality-2026-09-23.md).
