# Paper 단계 관찰 체크리스트

paper 워커를 2–3일 운영하며 기록합니다. shadow 승격 전에 완료하세요.

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
