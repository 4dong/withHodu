# 공개 전환 체크리스트

작성일: 2026-09-11 · 현재 저장소 상태: private

## 완료한 준비

| 항목 | 조치 |
| --- | --- |
| 보안 정보 | 커밋 이력 전체(14개 커밋, 삭제된 파일 포함)에서 API 키·토큰·개인키 패턴을 검사했고 발견되지 않음. `.env`와 키 저장 파일은 커밋된 적 없음 |
| 아카이브 | 논문(`~/PaperArchive`)과 자소서(`~/EssayArchive`)는 저장소 밖에 저장. `.gitignore`에 아카이브 폴더, PDF, DB, ZIP, 키 저장 파일 추가 |
| 로컬 경로 | 코드·테스트·문서의 `/Users/...` 경로를 없애고, 비공개 seed 폴더는 `ESSAY_SEED_DIR`(환경변수 또는 `.env`)로 지정 |
| 자소서 내용 | 오프라인 모의 답변에 들어 있던 참고 자소서 문장·수치를 없앰. 답변은 검색된 근거에서 수치와 문장을 뽑아 만들고, 테스트용 수치는 가상 값으로 교체 |
| seed 없는 환경 | 비공개 seed가 필요한 테스트 4개는 파일이 없으면 이유를 표시하고 건너뜀 |

## 검증 방법 (다시 실행할 때)

저장소 파일만 새 폴더에 복사하고, 빈 홈 폴더와 최소한의 환경변수로 실행한다.

```bash
PUB=$(mktemp -d)
git ls-files -co --exclude-standard | rsync -a --files-from=- ./ "$PUB/repo/"
mkdir -p "$PUB/home" && cd "$PUB/repo"
env -i PATH=/usr/bin:/bin HOME="$PUB/home" python3 -m unittest discover -s tests -t .
```

2026-09-11 결과: 기본 테스트 12개 통과. 자소서 테스트는 20개 통과, 4개는 seed가 없어 건너뜀. AppTest로 검색 화면과 자기소개서 작업실(탭 6개)을 띄웠을 때 예외 0건, 샘플 가져오기 버튼은 비활성. 비공개 seed가 있는 로컬에서는 24개 모두 통과.

보안 정보 재검사:

```bash
git log --all -p --no-color | grep -nE "AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY"
git grep -n "/Users/"
```

## 이력 정리 (2026-09-11)

- 기존 커밋 14개를 없애고 현재 파일만 담은 커밋 1개로 다시 시작함. 파일 내용(트리 해시)은 정리 전과 동일.
- `.agents/skills/`(파일 457개)는 사용하지 않아 저장소에서 제외하고 `.gitignore`에 추가함(로컬 파일은 유지).
- GitHub가 떨어져 나온 옛 커밋을 해시로 계속 보관하므로, 저장소를 삭제하고 같은 이름으로 다시 만든 뒤 새 커밋을 올림.
- 옛 이력은 저장소 밖 로컬 번들(`Anti-paper-history-backup-2026-09-11.bundle`)로만 보관. 공유하거나 올리지 않는다.

## 공개 전에 결정할 것

1. **작성자 이메일:** 커밋 작성자로 개인 이메일이 기록된다. 공개 전에 `git config user.email`을 GitHub noreply 주소로 바꾸면 이후 커밋부터 적용된다.
2. **라이선스:** 저장소에 `LICENSE` 파일이 없다. 공개 시 사용 조건을 정한다.
