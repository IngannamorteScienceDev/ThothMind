import { Link, useParams } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import type { SuiteRun, SuiteTickerResult } from "../shared/types/api";
import { loadSuiteRuns, loadSuiteTickerResults } from "../services/dataLoader";
import { adaptSuiteRuns, adaptSuiteTickerResults } from "../services/adapters";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function SuiteDetailPage() {
  const { configId } = useParams();
  const decodedConfig = decodeURIComponent(configId ?? "");

  const [suiteRuns, setSuiteRuns] = useState<SuiteRun[]>([]);
  const [tickerRows, setTickerRows] = useState<SuiteTickerResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);

      const [suiteRaw, tickerRaw] = await Promise.all([
        loadSuiteRuns(),
        loadSuiteTickerResults(),
      ]);

      setSuiteRuns(adaptSuiteRuns(suiteRaw));
      setTickerRows(adaptSuiteTickerResults(tickerRaw));
      setLoading(false);
    }

    bootstrap();
  }, []);

  const detail = useMemo(() => {
    const suite = suiteRuns.find((r) => r.config === decodedConfig) ?? null;
    const tickers = tickerRows.filter((r) => r.config === decodedConfig);

    const sortedByReturn = [...tickers].sort(
      (a, b) => (b.strat_total_return ?? -Infinity) - (a.strat_total_return ?? -Infinity)
    );

    const sortedByDrawdown = [...tickers].sort(
      (a, b) => (a.strat_max_drawdown ?? Infinity) - (b.strat_max_drawdown ?? Infinity)
    );

    const positiveCount = tickers.filter(
      (r) => typeof r.strat_total_return === "number" && (r.strat_total_return ?? 0) > 0
    ).length;

    const avgSharpeValues = tickers
      .map((r) => r.strat_sharpe)
      .filter((v): v is number => typeof v === "number");

    const avgSharpe =
      avgSharpeValues.length > 0
        ? avgSharpeValues.reduce((a, b) => a + b, 0) / avgSharpeValues.length
        : null;

    const avgReturnValues = tickers
      .map((r) => r.strat_total_return)
      .filter((v): v is number => typeof v === "number");

    const avgReturn =
      avgReturnValues.length > 0
        ? avgReturnValues.reduce((a, b) => a + b, 0) / avgReturnValues.length
        : null;

    return {
      suite,
      tickers,
      topTickers: sortedByReturn.slice(0, 6),
      worstDrawdowns: sortedByDrawdown.slice(0, 6),
      registryPreview: sortedByReturn.slice(0, 12),
      positiveCount,
      avgSharpe,
      avgReturn,
    };
  }, [suiteRuns, tickerRows, decodedConfig]);

  if (loading) {
    return <div className="empty-state">Loading suite detail…</div>;
  }

  if (!detail.suite) {
    return (
      <div className="page">
        <div className="empty-state">
          Suite config not found for <code>{decodedConfig}</code>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="section-hero">
        <div className="section-hero__content">
          <div className="section-label">Suite detail</div>
          <h1 className="section-hero__title">{detail.suite.config}</h1>
          <p className="section-hero__text">
            Detailed analytical view for one suite-level experiment. This page connects
            aggregate performance metrics with ticker-level outputs and provides a
            defendable interpretation layer for the selected configuration.
          </p>
          <div className="hero__chips">
            <span className="hero-chip">{detail.suite.stage}</span>
            <span className="hero-chip">{detail.suite.suite_mode}</span>
            <span className="hero-chip">{detail.suite.n_suite_tickers} instruments</span>
          </div>
        </div>

        <div className="section-hero__stats">
          <div className="mini-stat">
            <div className="mini-stat__label">Return</div>
            <div className="mini-stat__value">{fmt(detail.suite.return_metric_pct)}%</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Sharpe</div>
            <div className="mini-stat__value">{fmt(detail.suite.sharpe, 3)}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">p-value</div>
            <div className="mini-stat__value">{fmt(detail.suite.p_value_one_sided, 4)}</div>
          </div>
        </div>
      </section>

      <section className="snapshot-strip">
        <div className="snapshot-card">
          <div className="snapshot-card__label">Universe</div>
          <div className="snapshot-card__value">{detail.suite.n_suite_tickers}</div>
          <div className="snapshot-card__meta">Tickers included in this suite</div>
        </div>

        <div className="snapshot-card">
          <div className="snapshot-card__label">Average ticker return</div>
          <div className="snapshot-card__value">{fmt(detail.avgReturn)}%</div>
          <div className="snapshot-card__meta">Computed from per-ticker suite rows</div>
        </div>

        <div className="snapshot-card">
          <div className="snapshot-card__label">Average ticker sharpe</div>
          <div className="snapshot-card__value">{fmt(detail.avgSharpe, 4)}</div>
          <div className="snapshot-card__meta">Risk-adjusted average across visible rows</div>
        </div>

        <div className="snapshot-card">
          <div className="snapshot-card__label">Positive instruments</div>
          <div className="snapshot-card__value">{detail.positiveCount}</div>
          <div className="snapshot-card__meta">
            Tickers with positive strategy return in this configuration
          </div>
        </div>
      </section>

      <div className="metrics-strip">
        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Max drawdown</div>
          <div className="metrics-strip__title">{fmt(detail.suite.max_drawdown_pct)}%</div>
          <div className="metrics-strip__meta">
            Aggregate downside profile for this suite configuration
          </div>
        </div>

        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Defense-ready score</div>
          <div className="metrics-strip__title">
            {fmt(detail.suite.defense_ready_score, 3)}
          </div>
          <div className="metrics-strip__meta">
            Ranking heuristic, not a substitute for formal significance claims
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <section className="terminal-card">
          <div className="section-label">Top instruments</div>
          <h2 className="section-title">Highest return contributors</h2>
          <div className="mini-list">
            {detail.topTickers.map((row, idx) => (
              <div className="mini-list__item" key={`${row.ticker}-${idx}`}>
                <div>
                  <div className="mini-list__title">{row.ticker}</div>
                  <div className="mini-list__meta">
                    Sharpe {fmt(row.strat_sharpe, 4)} • p-value{" "}
                    {fmt(row.p_value_one_sided, 4)}
                  </div>
                </div>
                <div className="mini-list__value">{fmt(row.strat_total_return)}%</div>
              </div>
            ))}
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Risk concentration</div>
          <h2 className="section-title">Deepest drawdowns</h2>
          <div className="mini-list">
            {detail.worstDrawdowns.map((row, idx) => (
              <div className="mini-list__item" key={`${row.ticker}-${idx}`}>
                <div>
                  <div className="mini-list__title">{row.ticker}</div>
                  <div className="mini-list__meta">
                    Return {fmt(row.strat_total_return)} • Sharpe {fmt(row.strat_sharpe, 4)}
                  </div>
                </div>
                <div className="mini-list__value">{fmt(row.strat_max_drawdown)}%</div>
              </div>
            ))}
          </div>
        </section>

        <section className="terminal-card terminal-card--featured detail-grid__wide">
          <div className="section-label">Interpretation note</div>
          <h2 className="section-title">How to present this screen on defense</h2>
          <div className="research-annotation-grid">
            <div className="research-annotation">
              <div className="research-annotation__label">What this page proves</div>
              <div className="research-annotation__value">Result transparency</div>
              <div className="research-annotation__text">
                The system stores not only suite-level summary metrics, but also
                detailed instrument-level outputs for deeper analysis.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">Why it matters</div>
              <div className="research-annotation__value">Explainability</div>
              <div className="research-annotation__text">
                This supports interpretation of why a configuration looks strong or weak,
                instead of reducing the platform to one aggregate score.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">Research caution</div>
              <div className="research-annotation__value">Statistical honesty</div>
              <div className="research-annotation__text">
                Even visually strong returns should still be discussed together with
                p-value and drawdown, not as unconditional evidence of superiority.
              </div>
            </div>
          </div>
        </section>

        <section className="table-card table-card--terminal detail-grid__wide">
          <div className="table-card__header">
            <div>
              <div className="section-label">Ticker registry</div>
              <div className="table-card__title">Highest-return ticker preview</div>
            </div>
            <div className="table-card__meta">{detail.registryPreview.length} rows shown</div>
          </div>

          <div className="table-wrap">
            <table className="tm-table tm-table--terminal">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Status</th>
                  <th>Return</th>
                  <th>Sharpe</th>
                  <th>Drawdown</th>
                  <th>p-value</th>
                </tr>
              </thead>
              <tbody>
                {detail.registryPreview.map((row, idx) => (
                  <tr key={`${row.ticker}-${idx}`}>
                    <td>
                      <div className="cell-primary">{row.ticker}</div>
                    </td>
                    <td>{row.status ?? "—"}</td>
                    <td className="num-cell">{fmt(row.strat_total_return)}</td>
                    <td className="num-cell">{fmt(row.strat_sharpe, 4)}</td>
                    <td className="num-cell">{fmt(row.strat_max_drawdown)}</td>
                    <td className="num-cell">{fmt(row.p_value_one_sided, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className="detail-actions">
        <Link to="/suite-runs" className="detail-back-link">
          ← Back to suite registry
        </Link>
      </div>
    </div>
  );
}