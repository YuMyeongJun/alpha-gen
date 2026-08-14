import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { StagePills, type StagePillId } from "./StagePills";

const meta: Meta<typeof StagePills> = {
  title: "Common/StagePills",
  component: StagePills,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof StagePills>;

export const Interactive: Story = {
  render: () => {
    const [value, setValue] = useState<StagePillId>("paper");
    return <StagePills value={value} onChange={setValue} />;
  },
};

export const Disabled: Story = {
  args: { value: "live", disabled: true },
};
