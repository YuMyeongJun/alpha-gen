import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface IDetailModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export const DetailModal = ({ open, title, onClose, children }: IDetailModalProps) => {
  const { t } = useTranslation();
  if (!open) return null;

  return (
    <div className="scrim" onClick={onClose}>
      <div className="dialog dialog--wide" onClick={(event) => event.stopPropagation()}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>{title}</h3>
          <button type="button" className="btn btn--sm btn--ghost" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
        {children}
      </div>
    </div>
  );
};
