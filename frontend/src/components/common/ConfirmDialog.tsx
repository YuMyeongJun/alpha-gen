import { useTranslation } from "react-i18next";

export interface IConfirmDialogProps {
  open: boolean;
  title: string;
  body: string;
  danger?: boolean;
  confirmText?: string;
  cancelText?: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export const ConfirmDialog = ({
  open,
  title,
  body,
  danger = false,
  confirmText,
  cancelText,
  onCancel,
  onConfirm,
}: IConfirmDialogProps) => {
  const { t } = useTranslation();
  if (!open) return null;

  return (
    <div className="scrim" onClick={onCancel}>
      <div className="dialog" onClick={(event) => event.stopPropagation()}>
        <h3>{title}</h3>
        <p>{body}</p>
        <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="btn" onClick={onCancel}>
            {cancelText ?? t("common.cancel")}
          </button>
          <button type="button" className={`btn ${danger ? "btn--danger" : "btn--primary"}`} onClick={onConfirm}>
            {confirmText ?? t("common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
};
