# Alpha-Gen Ops Check

프로젝트 readiness를 한 번에 점검합니다.

## 실행

1. `.cursor/skills/alpha-gen-readiness/SKILL.md` skill을 읽고 그 절차를 따릅니다.
2. 가능하면 `alpha-gen` MCP tool을 사용합니다: `health_check`, `get_safety_policy`, `run_setup_check`, `run_backend_tests`.
3. MCP 미연결 시 로컬 명령으로 대체:
   - `py scripts/setup_check.py`
   - `py -m pytest tests/test_backend_*.py -q`
   - (선택) `py scripts/kis_smoke_test.py`, `py scripts/claude_smoke_test.py`

## 출력

skill에 정의된 **판정 표**를 한국어로 채우고, 최종 `READY` 또는 `NOT READY`와 차단 사유를 명시합니다.

서버가 꺼져 있으면 API 항목은 skip하고 로컬 점검 결과만으로 partial 보고합니다.
