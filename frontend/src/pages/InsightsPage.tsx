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
        .sort((a, b) => (b.return_metric_pct ?? -Infinity) - (a.return_metric_pct ?? -Infinity))[0] ??
      null;

    const bestSharpe =
      suiteRuns
        .filter((r) => typeof r.sharpe === "number")
        .sort((a, b) => (b.sharpe ?? -Infinity) - (a.sharpe ?? -Infinity))[0] ??
      null;

    const bestDefense =
      suiteRuns
        .filter((r) => typeof r.defense_ready_score === "number")
        .sort(
          (a, b) =>
            (b.defense_ready_score ?? -Infinity) - (a.defense_ready_score ?? -Infinity)
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
            (b.strat_total_return ?? -Infinity) - (a.strat_total_return ?? -Infinity)
        )[0] ?? null;

    const worstTicker =
      tickerRows
        .filter((r) => typeof r.strat_total_return === "number")
        .sort(
          (a, b) =>
            (a.strat_total_return ?? Infinity) - (b.strat_total_return ?? Infinity)
        )[0] ?? null;

    const positiveTickers = tickerRows.filter(
      (r) => typeof r.strat_total_return === "number" && (r.strat_total_return ?? 0) > 0
    ).length;

    const totalTickerRows = tickerRows.length || 1;
    const positiveShare = (positiveTickers / totalTickerRows) * 100;

    return {
      bestReturn,
      bestSharpe,
      bestDefense,
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
          <div className="section-label">Research conclusions</div>
          <h1 className="section-hero__title">Insights</h1>
          <p className="section-hero__text">
            This screen transforms loaded JSON artifacts into presentation-friendly analytical
            conclusions. It is intended as the narrative layer of the system: what the
            current results suggest, what they do not prove, and how the interface should be
            explained during defense.
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

      {loading ? <div className="empty-state">Loading insights…</div> : null}

      <div className="insight-story-grid">
        <section className="terminal-card terminal-card--featured">
          <div className="section-label">Primary conclusion</div>
          <h2 className="section-title">Best raw suite return</h2>
          <div className="insight-story-value">{insights.bestReturn?.config ?? "—"}</div>
          <p className="section-text">
            This configuration currently shows the highest loaded suite-level return:
            {" "}
            <strong>{fmt(insights.bestReturn?.return_metric_pct)}%</strong>.
            It should be presented as the strongest raw performance result in the current
            curated snapshot, not as unconditional proof of robust superiority.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Risk-adjusted conclusion</div>
          <h2 className="section-title">Best sharpe profile</h2>
          <div className="insight-story-value">{insights.bestSharpe?.config ?? "—"}</div>
          <p className="section-text">
            The strongest loaded risk-adjusted profile is currently associated with sharpe
            {" "}
            <strong>{fmt(insights.bestSharpe?.sharpe, 4)}</strong>.
            This is useful when explaining why raw return alone is not enough.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Heuristic ranking</div>
          <h2 className="section-title">Defense-ready leader</h2>
          <div className="insight-story-value">{insights.bestDefense?.config ?? "—"}</div>
          <p className="section-text">
            The interface ranking currently prioritizes this configuration with score
            {" "}
            <strong>{fmt(insights.bestDefense?.defense_ready_score, 3)}</strong>.
            This should be described as an internal presentation heuristic.
          </p>
        </section>

        <section className="terminal-card terminal-note terminal-note--warning">
          <div className="section-label">Statistical caution</div>
          <h2 className="section-title">What the system does not prove</h2>
          <p className="section-text">
            The minimum loaded one-sided p-value is <strong>{fmt(insights.minP, 4)}</strong>.
            Unless this value becomes convincingly low, the results should be presented as
            promising comparative outputs inside a research system, not as conclusive evidence
            of stable market outperformance.
          </p>
        </section>
      </div>

      <div className="insight-story-grid">
        <section className="terminal-card">
          <div className="section-label">Instrument highlight</div>
          <h2 className="section-title">Best ticker result</h2>
          <div className="insight-story-value">{insights.bestTicker?.ticker ?? "—"}</div>
          <p className="section-text">
            Observed under <strong>{insights.bestTicker?.config ?? "—"}</strong> with return
            {" "}
            <strong>{fmt(insights.bestTicker?.strat_total_return)}%</strong>.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Risk highlight</div>
          <h2 className="section-title">Worst ticker result</h2>
          <div className="insight-story-value">{insights.worstTicker?.ticker ?? "—"}</div>
          <p className="section-text">
            Observed under <strong>{insights.worstTicker?.config ?? "—"}</strong> with return
            {" "}
            <strong>{fmt(insights.worstTicker?.strat_total_return)}%</strong>.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Coverage signal</div>
          <h2 className="section-title">Positive ticker share</h2>
          <div className="insight-story-value">{fmt(insights.positiveShare)}%</div>
          <p className="section-text">
            This approximates how much of the loaded per-ticker registry remains above zero.
            It helps explain whether strong results are broad-based or concentrated.
          </p>
        </section>
      </div>

      <section className="terminal-card terminal-card--featured">
        <div className="section-label">Recommended defense narrative</div>
        <h2 className="section-title">How to talk about ThothMind</h2>

        <div className="pipeline-flow">
          <div className="pipeline-step">
            <div className="pipeline-step__index">01</div>
            <div>
              <div className="pipeline-step__title">Start from architecture</div>
              <div className="pipeline-step__text">
                Emphasize that the system is offline-first: Python computes experiments,
                React interprets them.
              </div>
            </div>
          </div>

          <div className="pipeline-step">
            <div className="pipeline-step__index">02</div>
            <div>
              <div className="pipeline-step__title">Show aggregate intelligence</div>
              <div className="pipeline-step__text">
                Present suite-level returns, sharpe, drawdown, and defense-ready ranking.
              </div>
            </div>
          </div>

          <div className="pipeline-step">
            <div className="pipeline-step__index">03</div>
            <div>
              <div className="pipeline-step__title">Go deeper into explainability</div>
              <div className="pipeline-step__text">
                Use Suite Detail and Ticker Explorer to show that results can be inspected,
                not just displayed.
              </div>
            </div>
          </div>

          <div className="pipeline-step">
            <div className="pipeline-step__index">04</div>
            <div>
              <div className="pipeline-step__title">End with scientific honesty</div>
              <div className="pipeline-step__text">
                Clarify that the system demonstrates architecture, experimentation, and
                interpretation — while statistical superiority still requires caution.
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}