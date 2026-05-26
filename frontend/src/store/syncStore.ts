import { create } from "zustand";
import type { SyncTone } from "@/models/type/commonType";

interface SyncState {
  label: string;
  note: string;
  tone: SyncTone;
  setSyncState: (label: string, note: string, tone?: SyncTone) => void;
}

export const useSyncStore = create<SyncState>((set) => ({
  label: "동기화 대기 중",
  note: "자동 갱신 준비 중",
  tone: "warning",
  setSyncState: (label, note, tone = "warning") => set({ label, note, tone }),
}));
