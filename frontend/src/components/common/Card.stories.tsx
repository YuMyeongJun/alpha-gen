import type { Meta, StoryObj } from "@storybook/react-vite";
import { Card } from "./Card";

const meta: Meta<typeof Card> = {
  title: "Common/Card",
  component: Card,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Card>;

export const Default: Story = {
  args: { title: "최근 사이클", children: <p style={{ margin: 0 }}>본문 내용이 여기 들어갑니다.</p> },
};

export const WithEyebrowAndRight: Story = {
  args: {
    eyebrow: "TOTAL ASSET",
    title: "자산 추이",
    right: <span style={{ fontSize: 12, color: "var(--ink-3)" }}>1개월</span>,
    children: <p style={{ margin: 0 }}>차트나 표가 들어가는 영역.</p>,
  },
};
