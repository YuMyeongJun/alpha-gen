import type { Meta, StoryObj } from "@storybook/react-vite";
import { ConfirmDialog } from "./ConfirmDialog";

const meta: Meta<typeof ConfirmDialog> = {
  title: "Common/ConfirmDialog",
  component: ConfirmDialog,
  tags: ["autodocs"],
  parameters: { docs: { story: { inline: false, iframeHeight: 260 } } },
  args: {
    open: true,
    onCancel: () => {},
    onConfirm: () => {},
  },
};
export default meta;

type Story = StoryObj<typeof ConfirmDialog>;

export const Default: Story = {
  args: { title: "매도 주문 실행", body: "삼성전자 10주를 시장가로 매도합니다." },
};

export const Danger: Story = {
  args: {
    title: "긴급 정지 해제",
    body: "긴급 정지를 해제하면 즉시 자동 주문이 재개될 수 있습니다.",
    danger: true,
    confirmText: "해제",
  },
};
