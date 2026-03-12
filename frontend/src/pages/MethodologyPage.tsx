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
          <div className="section-label">Architecture and methodology</div>
          <h1 className="section-hero__title">How ThothMind Works</h1>
          <p className="section-hero__text">
            ThothMind is built as an offline analytical system. It selects a curated
            instrument universe, executes multi-ticker experiments, aggregates
            configuration-level and ticker-level metrics, and publishes the results to a
            frontend layer intended for comparison, interpretation, and demonstration.
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
            {manifest ? "manifest available" : "manifest missing"}
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
            <div className="dataset-metric__value">
              {manifest?.total_expected ?? "—"}
            </div>
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
            <div className="freshness-card__label">Top composite ranking</div>
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
                  Raw stock and ETF histories are scanned and ranked by history depth,
                  recency, and data quality in order to form a curated research subset.
                </div>
              </div>
            </div>

            <div className="pipeline-step">
              <div className="pipeline-step__index">02</div>
              <div>
                <div className="pipeline-step__title">
                  Curated dataset materialization
                </div>
                <div className="pipeline-step__text">
                  Selected instruments are copied into an isolated curated dataset so
                  that subsequent experiments operate on a reproducible and controlled
                  input universe.
                </div>
              </div>
            </div>

            <div className="pipeline-step">
              <div className="pipeline-step__index">03</div>
              <div>
                <div className="pipeline-step__title">M8 suite batch execution</div>
                <div className="pipeline-step__text">
                  The backend executes multi-ticker configurations, produces
                  configuration-level summaries, collects ticker-level diagnostics, and
                  exports frontend-ready indexes.
                </div>
              </div>
            </div>

            <div className="pipeline-step">
              <div className="pipeline-step__index">04</div>
              <div>
                <div className="pipeline-step__title">
                  Frontend analytical interface
                </div>
                <div className="pipeline-step__text">
                  The React frontend loads published artifacts and renders a stable
                  dashboard for comparison, interpretation, and presentation.
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
                Configuration-level performance indicator summarizing total strategy
                result for a given experiment run.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">Sharpe</div>
              <div className="method-metric__text">
                Risk-adjusted indicator showing how much return is achieved per unit of
                variability.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">Max Drawdown %</div>
              <div className="method-metric__text">
                Historical maximum decline observed on the strategy path, used to
                characterize downside exposure.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">p-value</div>
              <div className="method-metric__text">
                Comparative statistical indicator. High values should not be interpreted
                as strong evidence of stable superiority.
              </div>
            </div>

            <div className="method-metric">
              <div className="method-metric__title">Composite score</div>
              <div className="method-metric__text">
                Internal ranking metric used for interface ordering and compact
                comparison. It does not replace formal statistical interpretation.
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Design principles</div>
          <h2 className="section-title">System design rationale</h2>

          <div className="research-annotation-grid">
            <div className="research-annotation">
              <div className="research-annotation__label">Reproducibility</div>
              <div className="research-annotation__value">Controlled universe</div>
              <div className="research-annotation__text">
                A curated subset limits uncontrolled runtime growth and supports a
                stable and repeatable analytical demonstration.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">
                Separation of concerns
              </div>
              <div className="research-annotation__value">
                Backend and frontend roles
              </div>
              <div className="research-annotation__text">
                Computational workloads remain in Python, while the interface focuses on
                structured interpretation and presentation of saved outputs.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">
                Demonstration stability
              </div>
              <div className="research-annotation__value">Precomputed artifacts</div>
              <div className="research-annotation__text">
                The system avoids heavy live calculations during a session and maintains
                predictable responsiveness in demonstration mode.
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Limitations</div>
          <h2 className="section-title">Scope of interpretation</h2>

          <div className="terminal-note terminal-note--warning">
            The current interface visualizes precomputed results on a historical dataset
            snapshot. It demonstrates system architecture, experiment orchestration, and
            analytical interpretation, but it should not be presented as a real-time
            trading terminal or as conclusive proof of statistically stable market
            outperformance.
          </div>
        </section>
      </div>
    </div>
  );
}