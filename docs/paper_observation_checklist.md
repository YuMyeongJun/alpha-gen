# Paper 단계 관찰 체크리스트

paper 워커를 2–3일 운영하며 기록합니다. shadow 승격 전에 완료하세요.

## Paper 안정화 루틴 (권장)

1. **uvicorn 1개만** 실행 (중복 기동 시 KIS 토큰 403/500 증가)
2. **워커 60초 주기** ON — 잔고·시그널·주문은 워커 사이클 중심
3. 콘솔 폴링만으로 KIS 잔고 sync **하지 않음** (paper는 worker/manual만 sync)
4. Audit에 `position_sync_failed` 연속 시 **5분 대기** 후 `py scripts/kis_smoke_test.py`
5. 하루 1회: `py scripts/paper_onboarding_check.py` + 긴급정지 ON/OFF 테스트

### .env 안정화 튜닝 (선택)

```env
PAPER_BROKER_SYNC_INTERVAL_SEC=300
KIS_API_MIN_INTERVAL_MS=400
BROKER_SYNC_INTERVAL_SEC=120
```

## 일일 기록

| 날짜 | Worker 사이클 | 시그널 | 주문 filled | rejected | 긴급정지 | 비고 |
|------|---------------|--------|-------------|----------|----------|------|
| | | | | | | |

## 확인 항목

### 데이터·시그널
- [ ] RSS 수집 정상 (audit에 news 관련 이벤트)
- [ ] Claude 감성 점수가 mock이 아닌 실 API 결과
- [ ] 시그널 패널에 BUY/WATCH 분포 합리적

### 주문·상태
- [ ] paper 주문이 `filled` 또는 `rejected`로 일관되게 기록
- [ ] 주문 상태 전이(audit) 누락 없음
- [ ] 손절/드로우다운 시 자동 주문 차단 확인

### 안전·운영
- [ ] 긴급정지 ON 시 신규 주문 거절
- [ ] 긴급정지 OFF 후 정상 복구
- [ ] 운영 콘솔 badge와 `/api/safety` policy 일치

### 장애
- [ ] KIS 토큰/시세 오류 시 audit critical/warning 기록
- [ ] worker 중지 후 재시작 가능

## 승격 판단

모든 항목 OK + `py scripts/paper_onboarding_check.py`에서 kis/claude pass → Cursor **`promote-stage`** 로 shadow 체크리스트 실행.

shadow 승격은 **운영자 확인 후** UI 또는 `POST /api/safety/stage`로만 진행합니다.
