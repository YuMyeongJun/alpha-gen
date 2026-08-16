import type { Meta, StoryObj } from "@storybook/react-vite";
import { Metric } from "./Metric";
import { Badge } from "./Badge";

const meta: Meta<typeof Metric> = {
  title: "Common/Metric",
  component: Metric,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Metric>;

export const Default: Story = {
  args: { label: "현금", value: "10,000,000", unit: "원", sub: "가용 비중 100.0%" },
};

export const Hero: Story = {
  args: {
    size: "hero",
    label: "총자산",
    value: "10,201,931",
    unit: "원",
    sub: <span style={{ color: "var(--green-600)" }}>+2.02% · 기준선 대비</span>,
  },
};

export const Danger: Story = {
  args: { label: "리스크 상태", value: "-16.00", unit: "%", tone: "danger", sub: "드로우다운 한계 초과" },
};

export const WithBadge: Story = {
  args: {
    label: "워커 상태",
    value: "실행 중",
    right: (
      <Badge tone="green" dot>
        실행중
      </Badge>
    ),
  },
};
