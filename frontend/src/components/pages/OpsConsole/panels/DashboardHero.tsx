import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { currency, formatRelative, percent, toneClass } from "@/utils/format";

export interface IDashboardHeroProps {
  data: IDashboardBundleRes;
}

export const DashboardHero = ({ data }: IDashboardHeroProps) => {
  const { portfolio, signals, system } = data;
  const workerRunning = Boolean(system.worker.running);
  const recentSignals = signals.signals || [];
  const buyCandidates = recentSignals.filter((signal) => signal.buy_signal).length;
  const drawdown = portfolio.risk?.drawdown_pct || 0;

  return (
    <section className="hero hero-compact">
      <div className="hero-copy-block">
        <p className="eyebrow">ALPHA-GEN WEB PRODUCT</p>
        <h2>운영 현황을 한눈에 보는 트레이딩 콘솔</h2>
        <p className="hero-copy">
          핵심 지표와 차트를 대시보드에 모아두었습니다. 상세 데이터는 각 메뉴에서 확인하세요.
        </p>
        <div className="summary-strip">
          <div className="summary-card">
            <div className="summary-label">오늘의 시그널</div>
            <div className="summary-value">{recentSignals.length}건</div>
            <div className="summary-note">매수 후보 {buyCandidates}건</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">리스크 상태</div>
            <div className={`summary-value ${toneClass(drawdown)}`}>{percent(drawdown)}</div>
            <div className="summary-note">{portfolio.risk?.sleep_mode ? "휴면 모드" : "정상 운영"}</div>
          </div>
          <div className="summary-card">
            <div className="summary-label">에이전트 워커</div>
            <div className="summary-value">{workerRunning ? "실행 중" : "대기 중"}</div>
            <div className={`summary-note ${workerRunning ? "live-note" : ""}`}>
              {workerRunning
                ? `다음 실행 ${formatRelative(system.worker.next_cycle_at)}`
                : system.worker.last_cycle_at
                  ? `마지막 실행 ${formatRelative(system.worker.last_cycle_at)}`
                  : "아직 실행 이력 없음"}
            </div>
          </div>
        </div>
      </div>
      <div className="hero-status">
        <div className="metric-card">
          <span>총자산</span>
          <strong>{currency(portfolio.total_asset)}원</strong>
        </div>
        <div className="metric-card">
          <span>현금</span>
          <strong>{currency(portfolio.cash)}원</strong>
        </div>
        <div className="metric-card">
          <span>워커</span>
          <strong className={workerRunning ? "running" : "stopped"}>{workerRunning ? "RUNNING" : "STOPPED"}</strong>
        </div>
      </div>
    </section>
  );
};
