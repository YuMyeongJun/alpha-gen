import type { Meta, StoryObj } from "@storybook/react-vite";
import { Icon, type IconName } from "./Icon";

const ALL_NAMES: IconName[] = [
  "dashboard", "portfolio", "signal", "orders", "backtest", "audit", "system",
  "stocks", "play", "pause", "refresh", "bolt", "stop", "warn", "sun", "moon", "menu",
];

const meta: Meta<typeof Icon> = {
  title: "Common/Icon",
  component: Icon,
  tags: ["autodocs"],
  argTypes: {
    name: { control: "select", options: ALL_NAMES },
  },
};
export default meta;

type Story = StoryObj<typeof Icon>;

export const Default: Story = { args: { name: "dashboard", size: 24 } };

export const AllIcons: Story = {
  render: () => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 16 }}>
      {ALL_NAMES.map((name) => (
        <div key={name} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <Icon name={name} size={22} />
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{name}</span>
        </div>
      ))}
    </div>
  ),
};
