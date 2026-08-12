import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { Card, PageHeader } from "@/components/common";
import apiClient from "@/modules/apiClient";

// ── 타입 ──────────────────────────────────────────────────────────────────────

interface StockItem {
  code: string;
  name: string;
  session: "KR" | "US";
  source: "config" | "custom";
  keywords: string[];
  exchange?: string;
  news_topic?: string;
  added_at?: string;
}

interface AddForm {
  code: string;
  name: string;
  session: "KR" | "US";
  keywords: string;
  exchange: "NASD" | "NYSE" | "AMEX";
  news_topic: string;
}

const STOCKS_QUERY_KEY = ["stocks"];

async function fetchStocks(): Promise<{ stocks: StockItem[]; custom_count: number }> {
  const res = await apiClient.get("/api/stocks");
  return res.data;
}

async function addStock(payload: Omit<AddForm, "keywords"> & { keywords: string[] }): Promise<StockItem> {
  const res = await apiClient.post("/api/stocks", payload);
  return res.data.stock;
}

async function removeStock(session: string, code: string): Promise<void> {
  await apiClient.delete(`/api/stocks/${session}/${code}`);
}

// ── 컴포넌트 ──────────────────────────────────────────────────────────────────

export const StocksPanel = () => {
  // const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"KR" | "US">("KR");
  const [confirmDelete, setConfirmDelete] = useState<StockItem | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: STOCKS_QUERY_KEY,
    queryFn: fetchStocks,
    staleTime: 30_000,
  });

  const addMutation = useMutation({
    mutationFn: (payload: Omit<AddForm, "keywords"> & { keywords: string[] }) => addStock(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STOCKS_QUERY_KEY });
      toast.success("종목이 추가되었습니다.");
      reset();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "추가 실패";
      toast.error(msg);
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({ session, code }: { session: string; code: string }) => removeStock(session, code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STOCKS_QUERY_KEY });
      toast.success("종목이 삭제되었습니다.");
      setConfirmDelete(null);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "삭제 실패";
      toast.error(msg);
      setConfirmDelete(null);
    },
  });

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<AddForm>({
    defaultValues: { code: "", name: "", session: "KR", keywords: "", exchange: "NASD", news_topic: "" },
  });

  const watchSession = watch("session");

  const onSubmit = (values: AddForm) => {
    const keywords = values.keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    addMutation.mutate({
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      session: values.session,
      keywords,
      exchange: values.exchange,
      news_topic: values.news_topic.trim(),
    });
  };

  const stocks = data?.stocks ?? [];
  const tabStocks = stocks.filter((s) => s.session === tab);
  const configStocks = tabStocks.filter((s) => s.source === "config");
  const customStocks = tabStocks.filter((s) => s.source === "custom");

  return (
    <>
      <PageHeader
        title="종목 관리"
        subtitle={`분석·자동매매 대상 종목을 조회하고 커스텀 종목을 추가·삭제합니다. (기본 ${stocks.filter((s) => s.source === "config").length}개 · 추가 ${data?.custom_count ?? 0}개)`}
      />

      {/* 탭 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {(["KR", "US"] as const).map((s) => (
          <button
            key={s}
            className={`btn btn--sm${tab === s ? " btn--primary" : " btn--ghost"}`}
            onClick={() => setTab(s)}
          >
            {s === "KR" ? "🇰🇷 국내 (KR)" : "🇺🇸 미국 (US)"}
          </button>
        ))}
      </div>

      {/* 커스텀 종목 */}
      {customStocks.length > 0 && (
        <Card style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>📌 직접 추가한 종목</div>
          <table className="table">
            <thead>
              <tr>
                <th>코드</th>
                <th>종목명</th>
                <th>키워드</th>
                {tab === "US" && <th>거래소</th>}
                <th style={{ width: 70 }}></th>
              </tr>
            </thead>
            <tbody>
              {customStocks.map((s) => (
                <tr key={s.code}>
                  <td className="mono">{s.code}</td>
                  <td>{s.name}</td>
                  <td className="muted" style={{ fontSize: 12 }}>
                    {s.keywords.slice(0, 4).join(", ") || "-"}
                  </td>
                  {tab === "US" && <td className="mono muted">{s.exchange ?? "NASD"}</td>}
                  <td>
                    {confirmDelete?.code === s.code ? (
                      <span style={{ display: "flex", gap: 4 }}>
                        <button
                          className="btn btn--sm btn--danger"
                          onClick={() => removeMutation.mutate({ session: s.session, code: s.code })}
                          disabled={removeMutation.isPending}
                        >
                          확인
                        </button>
                        <button className="btn btn--sm btn--ghost" onClick={() => setConfirmDelete(null)}>
                          취소
                        </button>
                      </span>
                    ) : (
                      <button className="btn btn--sm btn--ghost" onClick={() => setConfirmDelete(s)}>
                        삭제
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* 기본 종목 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          📋 기본 종목 ({configStocks.length}개)
          <span className="muted" style={{ fontSize: 11, fontWeight: 400, marginLeft: 6 }}>
            config에 하드코딩된 종목 — 삭제 불가
          </span>
        </div>
        {isLoading ? (
          <div className="muted" style={{ padding: "12px 0" }}>불러오는 중…</div>
        ) : configStocks.length === 0 ? (
          <div className="empty-state">종목이 없습니다.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>코드</th>
                <th>종목명</th>
                <th>주요 키워드</th>
                {tab === "US" && <th>거래소</th>}
              </tr>
            </thead>
            <tbody>
              {configStocks.map((s) => (
                <tr key={s.code}>
                  <td className="mono">{s.code}</td>
                  <td>{s.name}</td>
                  <td className="muted" style={{ fontSize: 12 }}>
                    {s.keywords.slice(0, 4).join(", ") || "-"}
                  </td>
                  {tab === "US" && <td className="mono muted">{s.exchange ?? "NASD"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* 종목 추가 폼 */}
      <Card>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>➕ 종목 추가</div>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
            {/* 세션 */}
            <div>
              <label className="label">세션</label>
              <select className="input" {...register("session")}>
                <option value="KR">🇰🇷 국내 (KR)</option>
                <option value="US">🇺🇸 미국 (US)</option>
              </select>
            </div>

            {/* 거래소 (US만) */}
            <div style={{ visibility: watchSession === "US" ? "visible" : "hidden" }}>
              <label className="label">거래소</label>
              <select className="input" {...register("exchange")}>
                <option value="NASD">NASDAQ</option>
                <option value="NYSE">NYSE</option>
                <option value="AMEX">AMEX</option>
              </select>
            </div>

            {/* 종목 코드 */}
            <div>
              <label className="label">
                종목코드 <span style={{ color: "var(--red-500)" }}>*</span>
              </label>
              <input
                className={`input${errors.code ? " input--error" : ""}`}
                placeholder={watchSession === "KR" ? "예: 005380" : "예: NVDA"}
                {...register("code", { required: "필수 항목입니다" })}
              />
              {errors.code && <div className="form-error">{errors.code.message}</div>}
            </div>

            {/* 종목명 */}
            <div>
              <label className="label">
                종목명 <span style={{ color: "var(--red-500)" }}>*</span>
              </label>
              <input
                className={`input${errors.name ? " input--error" : ""}`}
                placeholder={watchSession === "KR" ? "예: 현대차" : "예: NVIDIA"}
                {...register("name", { required: "필수 항목입니다" })}
              />
              {errors.name && <div className="form-error">{errors.name.message}</div>}
            </div>

            {/* 키워드 */}
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="label">
                검색 키워드
                <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>
                  (쉼표로 구분, 뉴스 감성분석에 사용)
                </span>
              </label>
              <input
                className="input"
                placeholder={watchSession === "KR" ? "예: 현대차, Hyundai, 전기차, EV" : "예: NVIDIA, GPU, AI chip, data center"}
                {...register("keywords")}
              />
            </div>

            {/* 커스텀 뉴스 토픽 (선택) */}
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="label">
                커스텀 뉴스 토픽
                <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>
                  (비우면 키워드로 자동 생성)
                </span>
              </label>
              <input
                className="input"
                placeholder="예: Hyundai EV electric vehicle battery Korea stock"
                {...register("news_topic")}
              />
            </div>
          </div>

          <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10 }}>
            <button className="btn btn--primary" type="submit" disabled={addMutation.isPending}>
              {addMutation.isPending ? "추가 중…" : "종목 추가"}
            </button>
            <span className="muted" style={{ fontSize: 12 }}>
              추가 후 다음 분석 사이클부터 뉴스 수집·시그널 생성이 시작됩니다.
            </span>
          </div>
        </form>
      </Card>
    </>
  );
};
