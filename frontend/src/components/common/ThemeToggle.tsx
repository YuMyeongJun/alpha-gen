import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "@/components/common/Icon";

/**
 * 라이트/다크 테마 토글.
 * - 명시 선택은 <html data-theme="..."> + localStorage("theme")에 저장.
 * - 미선택 시 OS 설정(prefers-color-scheme)을 따른다 (styles.scss 참조).
 * FOUC 방지 초기 적용은 index.html의 인라인 스크립트가 담당한다.
 */
type ThemeMode = "light" | "dark";

const STORAGE_KEY = "theme";

const readInitialTheme = (): ThemeMode => {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  const prefersDark =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
};

export const ThemeToggle = () => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<ThemeMode>(readInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* localStorage 비활성 환경 무시 */
    }
  }, [mode]);

  const next = mode === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="btn btn--ghost btn--sm theme-toggle"
      onClick={() => setMode(next)}
      aria-label={t("theme.toggle", { defaultValue: "테마 전환" })}
      title={t(`theme.${next}`, { defaultValue: next === "dark" ? "다크" : "라이트" })}
    >
      <Icon name={mode === "dark" ? "sun" : "moon"} size={14} />
    </button>
  );
};
