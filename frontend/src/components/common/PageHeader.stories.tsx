import type { Meta, StoryObj } from "@storybook/react-vite";
import { PageHeader } from "./PageHeader";
import { Badge } from "./Badge";

const meta: Meta<typeof PageHeader> = {
  title: "Common/PageHeader",
  component: PageHeader,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof PageHeader>;

export const Default: Story = {
  args: { title: "포트폴리오", subtitle: "보유 종목과 평가손익을 확인하세요." },
};

export const WithEyebrowAndRight: Story = {
  args: {
    eyebrow: "ALPHA-GEN · 운영 콘솔",
    title: "백테스트",
    subtitle: "전략을 실데이터로 검증합니다.",
    right: <Badge tone="green">모의</Badge>,
  },
};
