import { useOutletContext } from "react-router-dom";
import type { IOpsConsoleOutletContext } from "@/components/pages/OpsConsole/OpsConsoleLayout";

export const useOpsConsoleContext = () => useOutletContext<IOpsConsoleOutletContext>();
