import type { Meta, StoryObj } from "@storybook/react-vite";
import { ThemeToggle } from "./ThemeToggle";

const meta: Meta<typeof ThemeToggle> = {
  title: "Common/ThemeToggle",
  component: ThemeToggle,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof ThemeToggle>;

export const Default: Story = {};
