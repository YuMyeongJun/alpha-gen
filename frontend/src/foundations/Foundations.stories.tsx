import type { Meta, StoryObj } from "@storybook/react-vite";
import { Foundations } from "./Foundations";

const meta: Meta<typeof Foundations> = {
  title: "Foundations/Design Tokens",
  component: Foundations,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof Foundations>;

export const AllTokens: Story = {};
