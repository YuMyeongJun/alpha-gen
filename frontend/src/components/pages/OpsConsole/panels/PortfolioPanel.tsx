import { Badge } from "@/components/common/Badge";
import { OpsConsoleCharts } from "@/components/pages/OpsConsole/OpsConsoleCharts";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { currency, percent, toneClass } from "@/utils/format";

export interface IPortfolioPanelProps {
  portfolio: IDashboardBundleRes["portfolio"];
  signals: IDashboardBundleRes["signals"];
}

export const PortfolioPanel = ({ portfolio, signals }: IPortfolioPanelProps) => {
  const drawdown = portfolio.risk?.drawdown_pct || 0;

  return (
    <article className="panel panel-portfolio">
      <div className="panel-header">
        <h3>포트폴리오</h3>
        <Badge>{portfolio.positions.length} positions</Badge>
      </div>
      <div className="panel-overview">
        <div className="mini-stat">
          <div className="mini-stat-label">보유 포지션</div>
          <div className="mini-stat-value">{portfolio.positions.length}개</div>
        </div>
        <div className="mini-stat">
          <div className="mini-stat-label">드로우다운</div>
          <div className={`mini-stat-value ${toneClass(drawdown)}`}>{percent(drawdown)}</div>
        </div>
        <div className="mini-stat">
          <div className="mini-stat-label">손절 감시</div>
          <div className="mini-stat-value">{portfolio.risk?.stop_loss_count || 0}건</div>
        </div>
        <div className="mini-stat">
          <div className="mini-stat-label">운영 상태</div>
          <div className="mini-stat-value">{portfolio.risk?.sleep_mode ? "휴면" : "활성"}</div>
        </div>
      </div>
      <OpsConsoleCharts portfolio={portfolio} signals={signals} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th>코드</th>
              <th>세션</th>
              <th>수량</th>
              <th>평단</th>
              <th>현재가</th>
              <th>손익률</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.positions.length ? (
              portfolio.positions.map((item) => {
                const pnlPct = item.avg_price
                  ? ((item.last_price - item.avg_price) / item.avg_price) * 100
                  : 0;
                return (
                  <tr key={`${item.stock_code}-${item.session}`}>
                    <td>{item.stock_name}</td>
                    <td>{item.stock_code}</td>
                    <td>{item.session}</td>
                    <td>{item.qty}</td>
                    <td>{currency(item.avg_price)}</td>
                    <td>{currency(item.last_price)}</td>
                    <td className={toneClass(pnlPct)}>{percent(pnlPct)}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={7}>
                  <div className="empty-state">아직 보유 포지션이 없습니다.</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </article>
  );
};
