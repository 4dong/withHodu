# 호두랑 시작 화면 — 구현·검증 기록

2026-09-11 · 로컬 Streamlit 앱 · `senior-ui-ux-orchestrator` → `webapp-ui-skill`

## 구현 완료

- `ui/home.py`: 시작 화면, 실제 작업공간 진입, 읽던 논문 이어 읽기, 움직임 설정 보존.
- `ui/home.css`: 홈에 한정된 종이색·초록 테마, 기준 이미지 표시, 가벼운 환영 동작, 반응형 배치.
- `app.py`: 새 세션에서 홈으로 진입.
- `ui/sidebar.py`: 시작 화면 복귀와 홈에서 선택한 작업공간 연결.
- `tests/test_hodu_home.py`: 네트워크 호출 없이 화면 이동과 세션 보존 검사. 자소서 저장소는 임시 폴더로 격리.
- [전체 화면 설계](withhodu-screen-storyboard.md): S00~S15, 기능별 로딩·성공·오류·빈 화면·전환·후속 자산 계약.

## Ran — 실제 실행한 검증

| 검증 | 결과 | 근거 |
| --- | --- | --- |
| `python3 -m unittest tests.test_hodu_home -v` | 3개 테스트 통과: 세 입구와 복귀, 모션 설정 유지, 검색 방문 후 읽던 논문·페이지·번역 보존 | [테스트](../../tests/test_hodu_home.py), 로컬 로그 `scratch/hodu-home-verification/apptest.txt` |
| 로컬 Chrome headless + CDP | 1280×900 / 390×844에서 렌더링, 가로 넘침 없음 | [데스크톱](previews/home-desktop.png), [모바일 상단](previews/home-mobile.png), [모바일 하단](previews/home-mobile-bottom.png) |
| 브라우저 상호작용 | 논문 검색 진입·홈 복귀 성공 | [결과 JSON](previews/home-checks.json) |
| 키보드 Tab | 주 동작 버튼 도달, solid 초점 테두리 확인 | [초점 화면](previews/home-keyboard-focus.png), 결과 JSON |
| OS 모션 감소 에뮬레이션 | 호두 animation-name이 `none` | 결과 JSON |
| 스킬 `visual_smoke_test.mjs` | localhost:8501 HTTP 200, HTML 존재 | `scratch/hodu-home-verification/http/summary.json` |
| 스킬 `check_state_coverage.ts --root ui` | CSS 1개만 검사, focus 외 마커 미검출. 이 도구 결과는 통과가 아님 | `scratch/hodu-home-verification/state-coverage.json` |
| `git diff --check` | 공백 오류 없음 | 실행 결과 |

상태 마커 검사기는 Python/Streamlit의 실행 상태를 판별하지 못하므로, 미검출 결과를 상태 부재로 단정하지 않았다. 홈의 상태별 적용 여부는 스토리보드 5절과 AppTest 결과로 구분했다. HTTP 검사 스크립트 자체에는 브라우저 드라이버가 없으므로 스크린샷은 별도의 로컬 Chrome CDP로 확인했다.

## Manual — 화면을 보고 확인

- 기존 레퍼런스의 정면·물어오기·독서·정리 자세가 각각 적절한 입구에 표시된다.
- 데스크톱 세 버튼은 동일한 높이에 정렬되며, 호두와 안내 문구가 겹치지 않는다.
- 모바일에서는 작은 환영 호두 옆에 안내 문구를 두고 첫 작업 버튼을 첫 화면 안에 배치했다.
- 제목 앵커 링크는 홈에서 숨겨 불필요한 탭 이동과 링크 아이콘을 제거했다.
- 기준표에 포함된 밝은 배경은 CSS 합성과 필터로 정리했다. 전용 투명 스프라이트로 정리한 상태는 아니다.

## Skipped / Planned

- 외부 검색·다운로드·번역 API 실행은 생략: 이번 변경은 홈과 라우팅이며 외부 요청을 만들 필요가 없다.
- 전체 앱의 호두 테마, 실제 프레임별 애니메이션 및 전환 효과는 설계 완료, 구현 예정.
- 전체 접근성 감사, 스크린리더 실기, Lighthouse 성능 점수는 실행하지 않았다. 키보드·모션·가로 넘침 확인을 전체 접근성 인증으로 간주하지 않는다.
- 읽기 복원은 현재 Streamlit 세션 안에서 제공한다. 브라우저 세션 종료 후 페이지까지 복구하는 영구 저장 기능은 이번 범위에 없다.

로컬 자료만 사용했으며 코드·스크린샷·개인 문서를 외부 디자인 서비스에 업로드하지 않았다.
