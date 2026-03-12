import { useEffect, useState } from "react";
import type { ArtifactFreshness, CuratedManifest } from "../shared/types/api";
import { loadArtifactFreshness, loadCuratedManifest } from "../services/dataLoader";

function prettyDate(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function MethodologyPage() {
  const [manifest, setManifest] = useState<CuratedManifest | null>(null);
  const [freshness, setFreshness] = useState<ArtifactFreshness | null>(null);

  useEffect(() => {
    async function bootstrap() {
      const [manifestRaw, freshnessRaw] = await Promise.all([
        loadCuratedManifest(),
        loadArtifactFreshness(),
      ]);

      setManifest(manifestRaw);
      setFreshness(freshnessRaw);
    }

    bootstrap();
  }, []);

  return (
    <div className="page">
      <section className="section-hero">
        <div className="section-hero__content">
          <div className="section-label">System methodology</div>
          <h1 className="section-hero__title">How ThothMind Works</h1>
          <p className="section-hero__text">
            ThothMind is structured as an offline-first research system. It builds a
            curated instrument universe, executes precomputed multi-ticker experiments,
            aggregates suite-level and per-ticker metrics, and exposes the results through
            an analytical interface designed for interpretation and defense presentation.
          </p>
        </div>

        <div className="section-hero__stats">
          <div className="mini-stat">
            <div className="mini-stat__label">Stage</div>
            <div className="mini-stat__value">M8</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Mode</div>
            <div className="mini-stat__value">True Multi</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Interface</div>
            <div className="mini-stat__value">React</div>
          </div>
        </div>
      </section>

      <section className="dataset-panel">
        <div className="dataset-panel__header">
          <div>
            <div className="section-label">Artifact lifecycle</div>
            <h2 className="section-title">Freshness and dataset provenance</h2>
          </div>
          <div className="dataset-status">
            {manifest ? "curated manifest loaded" : "manifest missing"}
          </div>
        </div>

        <div className="dataset-panel__grid">
          <div className="dataset-metric">
            <div className="dataset-metric__label">Stocks</div>
            <div className="dataset-metric__value">{manifest?.stocks_count ?? "—"}</div>
          </div>
          <div className="dataset-metric">
            <div className="dataset-metric__label">ETFs</div>
            <div className="dataset-metric__value">{manifest?.etfs_count ?? "—"}</div>
          </div>
          <div className="dataset-metric">
            <div className="dataset-metric__label">Expected</div>
            <div className="dataset-metric__value">{manifest?.total_expected ?? "—"}</div>
          </div>
          <div className="dataset-metric">
            <div className="dataset-metric__label">Copied</div>
            <div className="dataset-metric__value">{manifest?.total_copied ?? "—"}</div>
          </div>
        </div>

        <div className="freshness-grid">
          <div className="freshness-card">
            <div className="freshness-card__label">Suite index</div>
            <div className="freshness-card__value">
              {prettyDate(freshness?.suiteIndexLastModified)}
            </div>
          </div>
          <div className="freshness-card">
            <div className="freshness-card__label">Ticker index</div>
            <div className="freshness-card__value">
              {prettyDate(freshness?.tickerIndexLastModified)}
            </div>
          </div>
          <div className="freshness-card">
            <div className="freshness-card__label">Top by return</div>
            <div className="freshness-card__value">
              {prettyDate(freshness?.topReturnLastModified)}
            </div>
          </div>
          <div className="freshness-card">
            <div className="freshness-card__label">Top defense-ready</div>
            <div className="freshness-card__value">
              {prettyDate(freshness?.topDefenseLastModified)}
            </div>
          </div>
        </div>
      </section>

      <div className="methodology-grid">
        <section className="terminal-card terminal-card--featured">
          <div className="section-label">Architecture</div>
          <h2 className="section-title">Offline analytical pipeline</h2>

          <div className="pipeline-flow">
            <div className="pipeline-step">
              <div className="pipeline-step__index">01</div>
              <div>
                <div className="pipeline-step__title">Universe selection</div>
                <div className="pipeline-step__text">
                  Raw stock and ETF files are scanned and ranked by history depth,
                  recency, and data quality to produce a curated research subset.
                </div>
              </div>
            </div>

            <div className="pipeline-step">
              <div className="pipeline-step__index">02</div>
              <div>
                <div className="pipeline-step__title">Curated dataset materialization</div>
                <div className="pipeline-step__text">
                  Selected instruments are copied into an isolated curated dataset,
                  ensuring reproducible batch experiments and controlled demo scope.
                </div>
              </div>
            </div>

            <div className="pipeline-step">
              <div className="pipeline-step__index">03</div>
              <div>
                <div className="pipeline-step__title">M8 suite batch execution</div>
                <div className="pipeline-step__text">
                  The backend runs multi-ticker suite configurations, saves suite-level
                  summaries, ticker-level diagnostics, and post-processes them into
                  frontend-ready indexes.
                </div>
              </div>
            </div>

            <div className="pipeline-step">
              <div className="pipeline-step__index">04</div>
              <div>
                <div className="pipeline-step__title">Research terminal visualization</div>
                <div className="pipeline-step__text">
                  The React frontend loads JSON artifacts and renders a stable analytical
                  dashboard for comparison, interpretation, and live defense presentation.
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Metric interpretation</div>
          <h2 className="section-title">Core analytical signals</h2>

          <div className="method-metric-list">
            <div className="method-metric">
              <div className="method-metric__title">Return %</div>
              <div className="method-metric__text">
                Aggregate suite-level performance indicator for a given experiment configuration.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">Sharpe</div>
              <div className="method-metric__text">
                Risk-adjusted quality estimate showing how much performance is achieved per unit of variability.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">Max Drawdown %</div>
              <div className="method-metric__text">
                Historical worst decline observed in the strategy path. Useful for communicating downside risk.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">p-value</div>
              <div className="method-metric__text">
                Statistical comparison indicator. High values should not be interpreted as strong superiority evidence.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">Defense-ready score</div>
              <div className="method-metric__text">
                Internal ranking heuristic used for interface ordering. It is not a substitute for formal significance claims.
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Design principles</div>
          <h2 className="section-title">Why the system is structured this way</h2>

          <div className="research-annotation-grid">
            <div className="research-annotation">
              <div className="research-annotation__label">Reproducibility</div>
              <div className="research-annotation__value">Controlled universe</div>
              <div className="research-annotation__text">
                A curated subset prevents uncontrolled runtime growth and supports a stable thesis demo.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">Separation of concerns</div>
              <div className="research-annotation__value">Backend vs frontend</div>
              <div className="research-annotation__text">
                Heavy ML and backtesting remain in Python, while the UI focuses on interpretation and explanation.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">Defense strategy</div>
              <div className="research-annotation__value">Precomputed demo</div>
              <div className="research-annotation__text">
                This approach avoids long live computations and ensures that the interface remains responsive during presentation.
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Limitations</div>
          <h2 className="section-title">What should be stated honestly</h2>

          <div className="terminal-note terminal-note--warning">
            The current interface visualizes precomputed results on a historical dataset snapshot.
            It demonstrates system architecture, batch experimentation, and analytical interpretation,
            but it should not be presented as a real-time trading terminal or as proof of statistically
            conclusive market superiority.
          </div>
        </section>
      </div>
    </div>
  );
}