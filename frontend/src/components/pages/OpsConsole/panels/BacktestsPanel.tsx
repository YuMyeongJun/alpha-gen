import { Badge } from "@/components/common/Badge";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { currency, formatCompactDateTime, percent, toneClass } from "@/utils/format";

export interface IBacktestsPanelProps {
  runs: NonNullable<IDashboardBundleRes["backtests"]["runs"]>;
  onRunBacktest: () => void;
}

export const BacktestsPanel = ({ runs, onRunBacktest }: IBacktestsPanelProps) => (
  <article className="panel panel-backtests">
    <div className="panel-header">
      <h3>백테스트</h3>
      <button type="button" className="small-button" onClick={onRunBacktest}>
        최근 전략 백테스트
      </button>
    </div>
    <div className="list-stack">
      {!runs.length ? (
        <div className="list-card">백테스트 기록이 없습니다.</div>
      ) : (
        <>
          <div className="list-toolbar">
            <Badge>최근 {runs.length}회</Badge>
            <Badge tone={Number(runs[0].summary.total_return_pct) >= 0 ? "success" : "danger"}>
              최신 수익률 {percent(runs[0].summary.total_return_pct)}
            </Badge>
          </div>
          <div className="dense-table-wrap">
            <table className="dense-table">
              <thead>
                <tr>
                  <th>실행 시각</th>
                  <th>수익률</th>
                  <th>승률</th>
                  <th>거래 수</th>
                  <th>총 손익</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run, index) => (
                  <tr key={`${run.created_at}-${index}`}>
                    <td>{formatCompactDateTime(run.created_at)}</td>
                    <td className={Number(run.summary.total_return_pct) >= 0 ? "positive" : "negative"}>
                      {percent(run.summary.total_return_pct)}
                    </td>
                    <td>{Number(run.summary.win_rate).toFixed(1)}%</td>
                    <td>{run.summary.trade_count}건</td>
                    <td className={toneClass(run.summary.gross_pnl)}>{currency(run.summary.gross_pnl)}원</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  </article>
);
