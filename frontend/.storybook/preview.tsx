import type { Preview } from "@storybook/react-vite";
import { useEffect } from "react";
import "@/translations/i18n";
import "@/styles.scss";

const withTheme = (Story: React.ComponentType, context: { globals: { theme?: string } }) => {
  const theme = context.globals.theme === "dark" ? "dark" : "light";
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  return <Story />;
};

const preview: Preview = {
  parameters: {
    backgrounds: { disable: true },
    layout: "padded",
  },
  globalTypes: {
    theme: {
      description: "Light/dark theme",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: {
    theme: "light",
  },
  decorators: [withTheme],
};

export default preview;
