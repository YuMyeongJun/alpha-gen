import type { Meta, StoryObj } from "@storybook/react-vite";
import { MetricGrid } from "./MetricGrid";
import { Metric } from "./Metric";

const meta: Meta<typeof MetricGrid> = {
  title: "Common/MetricGrid",
  component: MetricGrid,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof MetricGrid>;

export const FourColumnWithHero: Story = {
  render: () => (
    <MetricGrid columns={4}>
      <Metric size="hero" label="총자산" value="10,201,931" unit="원" sub="+2.02% · 기준선 대비" />
      <Metric label="현금" value="10,000,000" unit="원" sub="가용 비중 100.0%" />
      <Metric label="워커 상태" value="중지됨" />
      <Metric label="리스크 상태" value="0.00" unit="%" />
    </MetricGrid>
  ),
};

export const TwoColumn: Story = {
  render: () => (
    <MetricGrid columns={2}>
      <Metric label="매수 후보" value="3" unit="건" />
      <Metric label="매도 후보" value="1" unit="건" />
    </MetricGrid>
  ),
};
