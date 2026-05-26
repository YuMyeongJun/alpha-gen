import { Badge } from "@/components/common/Badge";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { currency, shortText, toneClass } from "@/utils/format";

export interface ISignalsPanelProps {
  signals: IDashboardBundleRes["signals"]["signals"];
}

export const SignalsPanel = ({ signals }: ISignalsPanelProps) => {
  if (!signals.length) {
    return (
      <article className="panel panel-signals">
        <div className="panel-header">
          <h3>전략 시그널</h3>
          <Badge>최근 20건</Badge>
        </div>
        <div className="list-stack">
          <div className="list-card">아직 저장된 시그널이 없습니다.</div>
        </div>
      </article>
    );
  }

  const buyCount = signals.filter((signal) => signal.buy_signal).length;
  const avgSentiment = signals.reduce((sum, signal) => sum + Number(signal.sentiment_score || 0), 0) / signals.length;

  return (
    <article className="panel panel-signals">
      <div className="panel-header">
        <h3>전략 시그널</h3>
        <Badge>최근 20건</Badge>
      </div>
      <div className="list-stack">
        <div className="list-toolbar">
          <Badge>전체 {signals.length}건</Badge>
          <Badge tone="success">BUY {buyCount}건</Badge>
          <Badge tone="warning">WATCH {Math.max(signals.length - buyCount, 0)}건</Badge>
          <Badge>평균 감성 {avgSentiment.toFixed(2)}</Badge>
        </div>
        <div className="dense-table-wrap">
          <table className="dense-table">
            <thead>
              <tr>
                <th>종목</th>
                <th>세션</th>
                <th>액션</th>
                <th>감성</th>
                <th>현재가</th>
                <th>기술</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((signal) => (
                <tr key={`${signal.stock_code}-${signal.session}-${signal.current_price}`}>
                  <td>
                    <div className="cell-title">
                      {signal.stock_name} ({signal.stock_code})
                    </div>
                    <div className="cell-sub">{shortText(signal.technical_reason || "기술 신호 사유 없음")}</div>
                  </td>
                  <td>
                    <span className={`pill ${String(signal.session).toLowerCase()}`}>{signal.session}</span>
                  </td>
                  <td>
                    <Badge tone={signal.buy_signal ? "success" : "warning"}>{signal.buy_signal ? "BUY" : "WATCH"}</Badge>
                  </td>
                  <td className={toneClass(signal.sentiment_score)}>
                    {signal.sentiment_label} {signal.sentiment_score > 0 ? "+" : ""}
                    {signal.sentiment_score}
                  </td>
                  <td>{currency(signal.current_price)}원</td>
                  <td>{signal.technical_signal ? "통과" : "보류"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </article>
  );
};
