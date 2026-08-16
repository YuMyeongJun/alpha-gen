import type { Meta, StoryObj } from "@storybook/react-vite";
import { Badge } from "./Badge";

const meta: Meta<typeof Badge> = {
  title: "Common/Badge",
  component: Badge,
  tags: ["autodocs"],
  argTypes: {
    tone: {
      control: "select",
      options: ["green", "red", "blue", "gray", "amber", "success", "warning", "danger", "live"],
    },
  },
};
export default meta;

type Story = StoryObj<typeof Badge>;

export const Default: Story = { args: { children: "관망", tone: "gray" } };
export const Buy: Story = { args: { children: "매수", tone: "green", dot: true } };
export const Sell: Story = { args: { children: "매도", tone: "red", dot: true } };
export const Solid: Story = { args: { children: "거부", tone: "red", solid: true } };
export const AllTones: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {(["green", "red", "blue", "gray", "amber"] as const).map((tone) => (
        <Badge key={tone} tone={tone} dot>
          {tone}
        </Badge>
      ))}
    </div>
  ),
};
