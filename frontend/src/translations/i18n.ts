import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import en from "@/translations/en.json";
import ko from "@/translations/ko.json";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ko: { translation: ko },
      en: { translation: en },
    },
    lng: "ko",
    fallbackLng: "ko",
    supportedLngs: ["ko", "en"],
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "i18nextLng",
    },
    interpolation: { escapeValue: false },
  });

document.documentElement.lang = i18n.language || "ko";

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});

export default i18n;
