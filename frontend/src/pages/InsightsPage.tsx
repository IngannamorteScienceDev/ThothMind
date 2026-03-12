import { useEffect, useMemo, useState } from "react";
import type {
  CuratedManifest,
  SuiteRun,
  SuiteTickerResult,
} from "../shared/types/api";
import {
  loadCuratedManifest,
  loadSuiteRuns,
  loadSuiteTickerResults,
} from "../services/dataLoader";
import {
  adaptSuiteRuns,
  adaptSuiteTickerResults,
} from "../services/adapters";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function InsightsPage() {
  const [suiteRuns, setSuiteRuns] = useState<SuiteRun[]>([]);
  const [tickerRows, setTickerRows] = useState<SuiteTickerResult[]>([]);
  const [manifest, setManifest] = useState<CuratedManifest | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);

      const [suiteRaw, tickerRaw, manifestRaw] = await Promise.all([
        loadSuiteRuns(),
        loadSuiteTickerResults(),
        loadCuratedManifest(),
      ]);

      setSuiteRuns(adaptSuiteRuns(suiteRaw));
      setTickerRows(adaptSuiteTickerResults(tickerRaw));
      setManifest(manifestRaw);
      setLoading(false);
    }

    bootstrap();
  }, []);

  const insights = useMemo(() => {
    const bestReturn =
      suiteRuns
        .filter((r) => typeof r.return_metric_pct === "number")
        .sort(
          (a, b) =>
            (b.return_metric_pct ?? -Infinity) -
            (a.return_metric_pct ?? -Infinity)
        )[0] ?? null;

    const bestSharpe =
      suiteRuns
        .filter((r) => typeof r.sharpe === "number")
        .sort((a, b) => (b.sharpe ?? -Infinity) - (a.sharpe ?? -Infinity))[0] ??
      null;

    const bestComposite =
      suiteRuns
        .filter((r) => typeof r.defense_ready_score === "number")
        .sort(
          (a, b) =>
            (b.defense_ready_score ?? -Infinity) -
            (a.defense_ready_score ?? -Infinity)
        )[0] ?? null;

    const minP =
      suiteRuns
        .map((r) => r.p_value_one_sided)
        .filter((v): v is number => typeof v === "number")
        .sort((a, b) => a - b)[0] ?? null;

    const bestTicker =
      tickerRows
        .filter((r) => typeof r.strat_total_return === "number")
        .sort(
          (a, b) =>
            (b.strat_total_return ?? -Infinity) -
            (a.strat_total_return ?? -Infinity)
        )[0] ?? null;

    const worstTicker =
      tickerRows
        .filter((r) => typeof r.strat_total_return === "number")
        .sort(
          (a, b) =>
            (a.strat_total_return ?? Infinity) -
            (b.strat_total_return ?? Infinity)
        )[0] ?? null;

    const positiveTickers = tickerRows.filter(
      (r) =>
        typeof r.strat_total_return === "number" &&
        (r.strat_total_return ?? 0) > 0
    ).length;

    const totalTickerRows = tickerRows.length || 1;
    const positiveShare = (positiveTickers / totalTickerRows) * 100;

    return {
      bestReturn,
      bestSharpe,
      bestComposite,
      minP,
      bestTicker,
      worstTicker,
      positiveShare,
    };
  }, [suiteRuns, tickerRows]);

  return (
    <div className="page">
      <section className="section-hero">
        <div className="section-hero__content">
          <div className="section-label">Analytical conclusions</div>
          <h1 className="section-hero__title">Comparative Interpretation</h1>
          <p className="section-hero__text">
            This section synthesizes the current suite-level and instrument-level
            outputs into compact analytical conclusions. The goal is to present what
            the loaded snapshot indicates, how configurations differ from one another,
            and where statistical caution remains necessary.
          </p>
        </div>

        <div className="section-hero__stats">
          <div className="mini-stat">
            <div className="mini-stat__label">Stocks</div>
            <div className="mini-stat__value">{manifest?.stocks_count ?? "—"}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">ETFs</div>
            <div className="mini-stat__value">{manifest?.etfs_count ?? "—"}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Copied</div>
            <div className="mini-stat__value">{manifest?.total_copied ?? "—"}</div>
          </div>
        </div>
      </section>

      {loading ? <div className="empty-state">Loading analytical conclusions…</div> : null}

      <div className="insight-story-grid">
        <section className="terminal-card terminal-card--featured">
          <div className="section-label">Configuration ranking</div>
          <h2 className="section-title">Best return configuration</h2>
          <div className="insight-story-value">{insights.bestReturn?.config ?? "—"}</div>
          <p className="section-text">
            The highest suite-level return in the current snapshot is{" "}
            <strong>{fmt(insights.bestReturn?.return_metric_pct)}%</strong>. This
            configuration represents the strongest absolute performance result within
            the loaded registry.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Risk-adjusted ranking</div>
          <h2 className="section-title">Best Sharpe configuration</h2>
          <div className="insight-story-value">{insights.bestSharpe?.config ?? "—"}</div>
          <p className="section-text">
            The strongest risk-adjusted profile is associated with Sharpe{" "}
            <strong>{fmt(insights.bestSharpe?.sharpe, 4)}</strong>. This helps
            distinguish raw return leadership from more balanced performance.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Composite ranking</div>
          <h2 className="section-title">Best composite score configuration</h2>
          <div className="insight-story-value">
            {insights.bestComposite?.config ?? "—"}
          </div>
          <p className="section-text">
            The highest composite score in the current interface is{" "}
            <strong>{fmt(insights.bestComposite?.defense_ready_score, 3)}</strong>.
            This is an internal ordering signal intended for compact comparative
            ranking rather than a standalone scientific conclusion.
          </p>
        </section>

        <section className="terminal-card terminal-note terminal-note--warning">
          <div className="section-label">Statistical interpretation</div>
          <h2 className="section-title">Limits of evidence</h2>
          <p className="section-text">
            The minimum one-sided p-value in the loaded suite registry is{" "}
            <strong>{fmt(insights.minP, 4)}</strong>. This metric should be treated as
            a comparative diagnostic, not as unconditional proof of stable market
            outperformance.
          </p>
        </section>
      </div>

      <div className="insight-story-grid">
        <section className="terminal-card">
          <div className="section-label">Instrument highlight</div>
          <h2 className="section-title">Strongest visible instrument result</h2>
          <div className="insight-story-value">{insights.bestTicker?.ticker ?? "—"}</div>
          <p className="section-text">
            Observed under <strong>{insights.bestTicker?.config ?? "—"}</strong> with
            return <strong>{fmt(insights.bestTicker?.strat_total_return)}%</strong>.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Instrument risk</div>
          <h2 className="section-title">Weakest visible instrument result</h2>
          <div className="insight-story-value">{insights.worstTicker?.ticker ?? "—"}</div>
          <p className="section-text">
            Observed under <strong>{insights.worstTicker?.config ?? "—"}</strong> with
            return <strong>{fmt(insights.worstTicker?.strat_total_return)}%</strong>.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Coverage signal</div>
          <h2 className="section-title">Positive instrument share</h2>
          <div className="insight-story-value">{fmt(insights.positiveShare)}%</div>
          <p className="section-text">
            This indicator approximates the share of loaded ticker-level rows with a
            positive strategy outcome. It helps assess whether visible performance is
            broad-based or concentrated in a narrower subset of instruments.
          </p>
        </section>
      </div>

      <section className="terminal-card terminal-card--featured">
        <div className="section-label">Interpretation framework</div>
        <h2 className="section-title">How to read the current snapshot</h2>

        <div className="pipeline-flow">
          <div className="pipeline-step">
            <div className="pipeline-step__index">01</div>
            <div>
              <div className="pipeline-step__title">Start from architecture</div>
              <div className="pipeline-step__text">
                The backend performs precomputed experiment execution, while the
                frontend provides structured inspection of saved analytical outputs.
              </div>
            </div>
          </div>

          <div className="pipeline-step">
            <div className="pipeline-step__index">02</div>
            <div>
              <div className="pipeline-step__title">Compare configurations</div>
              <div className="pipeline-step__text">
                Suite-level metrics show how experiment variants differ by return,
                Sharpe, drawdown, and internal ranking score.
              </div>
            </div>
          </div>

          <div className="pipeline-step">
            <div className="pipeline-step__index">03</div>
            <div>
              <div className="pipeline-step__title">Inspect instrument dispersion</div>
              <div className="pipeline-step__text">
                Ticker-level outputs reveal whether visible results are distributed
                across the universe or concentrated in a limited subset.
              </div>
            </div>
          </div>

          <div className="pipeline-step">
            <div className="pipeline-step__index">04</div>
            <div>
              <div className="pipeline-step__title">Preserve statistical caution</div>
              <div className="pipeline-step__text">
                Current results should be interpreted as analytical evidence inside a
                historical research snapshot, not as a real-time guarantee of market
                superiority.
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}