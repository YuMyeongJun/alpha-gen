import type { Meta, StoryObj } from "@storybook/react-vite";
import { LanguageToggle } from "./LanguageToggle";

const meta: Meta<typeof LanguageToggle> = {
  title: "Common/LanguageToggle",
  component: LanguageToggle,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof LanguageToggle>;

export const Default: Story = {};
