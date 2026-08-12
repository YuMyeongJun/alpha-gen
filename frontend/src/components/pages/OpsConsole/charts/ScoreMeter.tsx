export interface IScoreMeterProps {
  /** 감성 점수 (-1 ~ +1 범위 가정, 벗어나면 clamp) */
  score: number;
}

/**
 * 양극(bipolar) 점수 미터. 중앙(0) 기준 오른쪽=양(초록)/왼쪽=음(빨강).
 * 시그널 리스트에서 감성 점수를 한눈에 스캔하기 위한 인라인 시각화.
 */
export const ScoreMeter = ({ score }: IScoreMeterProps) => {
  const value = Number.isFinite(score) ? score : 0;
  const clamped = Math.max(-1, Math.min(1, value));
  const half = Math.abs(clamped) * 50; // 트랙 절반(50%) 기준 채움 비율
  const positive = clamped >= 0;

  return (
    <div className="score-meter">
      <span className="score-meter__track" aria-hidden>
        <span className="score-meter__zero" />
        <span
          className="score-meter__fill"
          style={{
            width: `${half}%`,
            left: positive ? "50%" : undefined,
            right: positive ? undefined : "50%",
            background: positive ? "var(--green-500)" : "var(--red-500)",
          }}
        />
      </span>
      <span className={`score-meter__val ${positive ? "num-pos" : "num-neg"}`}>
        {value >= 0 ? "+" : ""}
        {value.toFixed(2)}
      </span>
    </div>
  );
};
