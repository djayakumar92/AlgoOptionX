import { Cockpit, MarketBar } from "../components/Cockpit";
import { MetricsRow } from "../components/MetricsRow";
import { OiChart } from "../components/OiChart";
import { OiHistoryChart } from "../components/OiHistoryChart";
import { OptionChainTable } from "../components/OptionChainTable";
import { SentimentPanel } from "../components/SentimentPanel";
import { SuggestionPanel } from "../components/SuggestionPanel";
import { fmtTime } from "../format";
import { useHealth } from "../hooks/useHealth";
import { useLiveState } from "../hooks/useLiveState";
import { useOiHistory } from "../hooks/useOiHistory";

// The old <Header> component lived here alone and duplicated what MarketBar
// now shows on every page (spot, tracked expiry, error banners), so it has
// been folded in rather than kept alongside. The one thing it had that the
// shared bar does not -- the poll-failure banner -- is kept below, because
// this is the page whose data the failing poll actually feeds.

export default function LivePage() {
  const health = useHealth();
  const { data, startingUp, fetchError } = useLiveState();
  const oiHistory = useOiHistory();

  const hasCycle = Boolean(data?.suggestion && data?.trend && data?.momentum && data?.sentiment);

  return (
    <Cockpit>
      <MarketBar title="Live Market">
        {health && <span>expiry {health.expiry}</span>}
        {data?.ts && <span>polled {fmtTime(data.ts)}</span>}
      </MarketBar>

      {startingUp && (
        <div className="banner banner-info">Waiting for the first poll cycle to complete...</div>
      )}
      {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
      {data?.error && (
        <div className="banner banner-warning">
          Poll failed, retrying: {data.error}
          {data.error_ts ? ` (as of ${fmtTime(data.error_ts)})` : ""}
        </div>
      )}

      {hasCycle && data && (
        <main className="cockpit-stack">
          <SuggestionPanel suggestion={data.suggestion!} />
          <MetricsRow trend={data.trend!} momentum={data.momentum!} sentiment={data.sentiment!} />
          <SentimentPanel sentiment={data.sentiment!} oiBehavior={data.oi_behavior!} />
          {oiHistory.data && <OiHistoryChart points={oiHistory.data.points} />}
          <OiChart rows={data.chain ?? []} />
          <OptionChainTable rows={data.chain ?? []} />
        </main>
      )}
    </Cockpit>
  );
}
