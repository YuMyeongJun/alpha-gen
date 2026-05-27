import { useTranslation } from "react-i18next";
import type { OperatingStage } from "@/models/type/commonType";

export type StagePillId = "shadow" | "paper" | "live";

export function stageToPill(stage: OperatingStage): StagePillId {
  if (stage === "paper") return "paper";
  if (stage === "live_limited" || stage === "live_full") return "live";
  return "shadow";
}

export function pillToStage(pill: StagePillId): OperatingStage {
  if (pill === "paper") return "paper";
  if (pill === "live") return "live_limited";
  return "shadow";
}

export interface IStagePillsProps {
  value: StagePillId;
  onChange?: (value: StagePillId) => void;
  disabled?: boolean;
}

export const StagePills = ({ value, onChange, disabled }: IStagePillsProps) => {
  const { t } = useTranslation();
  const stages: StagePillId[] = ["shadow", "paper", "live"];

  return (
    <div className="stage-pills" role="tablist">
      {stages.map((stage) => (
        <button
          key={stage}
          type="button"
          role="tab"
          data-stage={stage}
          disabled={disabled}
          className={`stage-pill${value === stage ? " active" : ""}`}
          onClick={() => onChange?.(stage)}
        >
          <span className="dot" />
          {t(`domain.stagePill.${stage}`)}
        </button>
      ))}
    </div>
  );
};
