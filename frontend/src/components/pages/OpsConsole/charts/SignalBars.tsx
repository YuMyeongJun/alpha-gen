export type SignalBarTone = "green" | "red" | "blue" | "gray";

export interface ISignalBarRow {
  key: string;
  label: string;
  value: number;
  tone: SignalBarTone;
}

export interface ISignalBarsProps {
  rows: ISignalBarRow[];
}

const TONE_COLOR: Record<SignalBarTone, string> = {
  green: "var(--green-500)",
  red: "var(--red-500)",
  blue: "var(--blue-500)",
  gray: "var(--ink-4)",
};

export const SignalBars = ({ rows }: ISignalBarsProps) => {
  const max = Math.max(1, ...rows.map((r) => r.value));

  return (
    <div>
      {rows.map((row) => (
        <div key={row.key} className="hbar-row">
          <div className="hbar-row__label">
            <span className="dot" style={{ background: TONE_COLOR[row.tone] }} />
            {row.label}
          </div>
          <div className="hbar-row__track">
            <div
              className="hbar-row__fill"
              style={{
                width: `${(row.value / max) * 100}%`,
                background: TONE_COLOR[row.tone],
              }}
            />
          </div>
          <div className="hbar-row__val">{row.value}건</div>
        </div>
      ))}
    </div>
  );
};
