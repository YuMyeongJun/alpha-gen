import ReactECharts from "echarts-for-react";
import type { IPortfolioRes, ISignalsListRes } from "@/models/interface/res/IDashboardRes";

export interface IOpsConsoleChartsProps {
  portfolio: IPortfolioRes;
  signals: ISignalsListRes;
}

export const OpsConsoleCharts = ({ portfolio, signals }: IOpsConsoleChartsProps) => {
  const equityValues = (portfolio.equity || []).map((item) => Number(item.total_asset || 0));
  const signalItems = signals.signals || [];
  const buyCount = signalItems.filter((item) => item.buy_signal).length;
  const watchCount = Math.max(signalItems.length - buyCount, 0);

  const equityOption = {
    grid: { left: 24, right: 24, top: 24, bottom: 32 },
    xAxis: { type: "category", show: false, data: equityValues.map((_, index) => index) },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } } },
    series: [
      {
        type: "line",
        smooth: true,
        areaStyle: { color: "rgba(109,124,255,0.18)" },
        lineStyle: { color: "#6d7cff", width: 3 },
        data: equityValues.length ? equityValues : [0],
      },
    ],
  };

  const signalOption = {
    grid: { left: 80, right: 24, top: 24, bottom: 24 },
    xAxis: { type: "value" },
    yAxis: {
      type: "category",
      data: ["BUY 후보", "WATCH"],
    },
    series: [
      {
        type: "bar",
        data: [buyCount, watchCount],
        itemStyle: { borderRadius: [0, 12, 12, 0], color: "#6d7cff" },
      },
    ],
  };

  return (
    <div className="chart-grid">
      <section className="chart-card">
        <div className="chart-card-header">
          <h4>총자산 추이</h4>
          <span className="section-caption">Equity</span>
        </div>
        <div className="chart-surface">
          {equityValues.length ? (
            <ReactECharts option={equityOption} style={{ height: 150 }} />
          ) : (
            <div className="chart-empty">표시할 자산 히스토리가 아직 없습니다.</div>
          )}
        </div>
      </section>
      <section className="chart-card">
        <div className="chart-card-header">
          <h4>시그널 분포</h4>
          <span className="section-caption">Signal mix</span>
        </div>
        <div className="chart-surface">
          {signalItems.length ? (
            <ReactECharts option={signalOption} style={{ height: 150 }} />
          ) : (
            <div className="chart-empty">시그널이 쌓이면 분포 차트가 나타납니다.</div>
          )}
        </div>
      </section>
    </div>
  );
};
