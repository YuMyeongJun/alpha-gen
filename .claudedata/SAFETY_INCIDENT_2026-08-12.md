# ⚠️ SAFETY INCIDENT — 2026-08-12 · 백엔드 live 무장 상태 발견

## 요약
UI 베이스라인 캡처를 위해 운영 백엔드(`python -m backend.app`, :8000)를 기동했더니, 런타임 안전 상태가 **실거래 무장(live-armed)** 이었고 서버 기동 시 **워커가 자동 재개**되어 실주문 가능 상태가 됐다. 즉시 백엔드 프로세스를 종료해 위험을 제거했다.

## 발견된 상태 (`/api/safety` 런타임)
| 항목 | 값 | 출처 |
|---|---|---|
| `promotion_stage` | `live_limited` (2026-06-03 저장) | `data/alpha_gen.sqlite3` · `agent_state` 테이블 |
| `emergency_stop.enabled` | `false` (2026-05-27) | `data/alpha_gen.sqlite3` |
| `allow_live_trading` | `true` | **`.env`** (config) |
| `mock_mode` | `false` | **`.env`** (config) |

두 겹 모두 무장: DB의 `promotion_stage=live_limited` + `.env`의 `ALLOW_LIVE_TRADING=true`. `SafetyService.ensure_order_allowed()`의 실거래 관문 조건(stage∈live_*, allow_live_trading, emergency_stop off, 한도 이내)이 모두 열려 있어, 장중·신선도·한도만 맞으면 실주문이 나갈 수 있었다.

**근거 코드:** `config/__init__.py` (기본값은 안전: MOCK_MODE 기본 True → stage mock 강제, 그러나 `.env`가 override) / `backend/app/services.py:203` `get_stage()`는 store의 `promotion_stage` 우선 / `create_app(auto_resume_worker=True)` (main.py L30,398) → 기동 시 워커 자동 재개(emergency_stop off라 재개됨).

## 취한 조치 (에이전트)
- 내가 기동한 백엔드 프로세스(:8000)를 **즉시 종료** → 워커 정지, 실주문 위험 제거. 시스템은 기동 전 상태(off)로 복귀.
- **안전 상태는 전혀 변경하지 않음**: stage/allow_live/emergency_stop/.env/DB 미수정, 주문 발생·취소 없음.

## 사람이 수행할 안전화 (에이전트가 하지 않음 — CLAUDE.md §4 관문 입력값)
1. `promotion_stage`를 `mock`(또는 `paper`)로 강등 — 운영 콘솔/CLI `SafetyService.set_stage()`.
2. `.env`에서 `ALLOW_LIVE_TRADING=false` (권장: `MOCK_MODE=true`).
3. 필요 시 `emergency_stop` 활성화.
4. 이 머신이 개발용이면, 왜 live_limited로 승격된 채 방치됐는지 원인 확인.

> 사용자 확인(2026-08-12): 이 live 무장 상태는 **의도되지 않음**.

## UI 작업용 안전 대안 (현재 사용 중)
격리 모크 샌드박스로 대체 — 실주문 위험 0:
- 런처: `<scratchpad>/ui_sandbox_server.py`
- 강제 env: `MOCK_MODE=true`, `ALLOW_LIVE_TRADING=false`, `EMERGENCY_STOP=true`, `ALPHA_GEN_DB_PATH=<scratchpad>/opsui_sandbox.sqlite3`(임시)
- `create_app(auto_resume_worker=False, bootstrap_legacy=False)` · 포트 **8010** (운영 8000과 분리)
- 검증: `/api/health` → `mode: mock`, `/api/safety` → stage mock·allow_live false·emergency_stop enabled. 운영 DB 미접촉.
- 재기동: 프로젝트 루트에서 `python "<scratchpad>/ui_sandbox_server.py"` → http://127.0.0.1:8010/
