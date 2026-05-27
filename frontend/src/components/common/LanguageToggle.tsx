import { useTranslation } from "react-i18next";
import i18n from "@/translations/i18n";

export const LanguageToggle = () => {
  const { i18n: i18nInstance } = useTranslation();
  const current = i18nInstance.language.startsWith("en") ? "en" : "ko";

  const setLanguage = (lng: "ko" | "en") => {
    void i18n.changeLanguage(lng);
  };

  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button
        type="button"
        className={`btn btn--sm${current === "ko" ? " btn--primary" : " btn--ghost"}`}
        onClick={() => setLanguage("ko")}
      >
        KO
      </button>
      <button
        type="button"
        className={`btn btn--sm${current === "en" ? " btn--primary" : " btn--ghost"}`}
        onClick={() => setLanguage("en")}
      >
        EN
      </button>
    </div>
  );
};
