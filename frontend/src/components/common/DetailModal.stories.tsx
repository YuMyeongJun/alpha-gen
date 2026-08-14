import type { Meta, StoryObj } from "@storybook/react-vite";
import { DetailModal } from "./DetailModal";

const meta: Meta<typeof DetailModal> = {
  title: "Common/DetailModal",
  component: DetailModal,
  tags: ["autodocs"],
  parameters: { docs: { story: { inline: false, iframeHeight: 320 } } },
  args: {
    open: true,
    onClose: () => {},
  },
};
export default meta;

type Story = StoryObj<typeof DetailModal>;

export const Default: Story = {
  args: {
    title: "주문 상세",
    children: (
      <dl className="kv">
        <dt>종목</dt>
        <dd>삼성전자 (005930)</dd>
        <dt>수량</dt>
        <dd>10주</dd>
        <dt>체결가</dt>
        <dd>75,000원</dd>
      </dl>
    ),
  },
};
