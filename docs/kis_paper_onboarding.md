# KIS 모의투자(paper) 온보딩

paper 단계까지의 설정·검증·운영 루틴입니다. Cursor plan과 동기화된 운영 가이드입니다.

## 빠른 시작

```powershell
# 1) .env 생성
copy env.example .env
# 또는: .\scripts\init_env.ps1

# 2) .env 편집 — KIS 모의 APP_KEY/SECRET, ACCOUNT_NO, ANTHROPIC_API_KEY

# 3) 통합 점검
py scripts/paper_onboarding_check.py

# 4) 개별 스모크
py scripts/kis_smoke_test.py
py scripts/claude_smoke_test.py
py scripts/setup_check.py
```

## .env 필수값 (paper)

| 변수 | paper 권장값 |
|------|----------------|
| `MOCK_MODE` | `false` |
| `IS_REAL_TRADING` | `false` |
| `ALLOW_LIVE_TRADING` | `false` |
| `ALPHA_GEN_STAGE` | `paper` |
| `KIS_APP_KEY` / `KIS_APP_SECRET` / `ACCOUNT_NO` | 모의투자 발급값 |
| `ANTHROPIC_API_KEY` | Claude API key |

`MOCK_MODE=true`(기본)이면 KIS 키가 있어도 mock으로 동작합니다.

## KIS 모의투자 연동

1. 한국투자증권 Open API 개발자센터 → **모의투자** 앱 등록
2. 모의투자 계좌 확인 → `ACCOUNT_NO`(8자리), `ACCOUNT_CODE`(01)
3. `py scripts/kis_smoke_test.py` → OAuth·시세·잔고 OK

## Claude API

- 키 없으면 뉴스 감성은 mock으로 동작
- `MOCK_MODE=false` + 키 설정 후 `py scripts/claude_smoke_test.py`

## 서버·UI

```powershell
cd frontend
npm install --legacy-peer-deps
npm run build
cd ..
py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

- 통합: http://127.0.0.1:8000
- 개발 UI: `npm run dev` → http://127.0.0.1:5173

## 운영 콘솔 paper 체크리스트

- [ ] 배지: Mock 아님, stage `paper`
- [ ] 설정: KIS·Claude OK
- [ ] Worker 1회 실행 / 60초 주기
- [ ] Audit에 cycle·order 이벤트
- [ ] 긴급정지 ON → 주문 거절 → OFF

Cursor: `ops-check`, `promote-stage` command

## paper 관찰 (2–3일)

[`docs/paper_observation_checklist.md`](./paper_observation_checklist.md) 참고.

안정화 후 `promote-stage`로 **shadow** 승격 검토.

## 하지 않을 것 (paper)

- `IS_REAL_TRADING=true`
- `ALLOW_LIVE_TRADING=true`
- shadow / live_* 승격 (paper 안정화 전)

자세한 단계 정의: [`operating_stages.md`](./operating_stages.md)
