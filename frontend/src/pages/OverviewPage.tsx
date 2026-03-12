import { useEffect, useMemo, useState } from "react";
import type {
  CuratedManifest,
  SuiteRun,
  SuiteTickerResult,
  TopRun,
} from "../shared/types/api";
import {
  loadCuratedManifest,
  loadSuiteRuns,
  loadSuiteTickerResults,
  loadTopByReturn,
  loadTopDefenseReady,
} from "../services/dataLoader";
import {
  adaptSuiteRuns,
  adaptSuiteTickerResults,
  adaptTopRuns,
} from "../services/adapters";
import KpiCard from "../widgets/kpi/KpiCard";
import SuiteReturnChart from "../widgets/charts/SuiteReturnChart";
import SuiteRiskChart from "../widgets/charts/SuiteRiskChart";
import ReturnDrawdownScatterChart from "../widgets/charts/ReturnDrawdownScatterChart";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function OverviewPage() {
  const [suiteRuns, setSuiteRuns] = useState<SuiteRun[]>([]);
  const [tickerRows, setTickerRows] = useState<SuiteTickerResult[]>([]);
  const [topReturn, setTopReturn] = useState<TopRun[]>([]);
  const [topComposite, setTopComposite] = useState<TopRun[]>([]);
  const [manifest, setManifest] = useState<CuratedManifest | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);

      const [suiteRaw, tickerRaw, topReturnRaw, topCompositeRaw, manifestRaw] =
        await Promise.all([
          loadSuiteRuns(),
          loadSuiteTickerResults(),
          loadTopByReturn(),
          loadTopDefenseReady(),
          loadCuratedManifest(),
        ]);

      setSuiteRuns(adaptSuiteRuns(suiteRaw));
      setTickerRows(adaptSuiteTickerResults(tickerRaw));
      setTopReturn(adaptTopRuns(topReturnRaw));
      setTopComposite(adaptTopRuns(topCompositeRaw));
      setManifest(manifestRaw);
      setLoading(false);
    }

    bootstrap();
  }, []);

  const stats = useMemo(() => {
    const runCount = suiteRuns.length;

    const bestReturnRow =
      suiteRuns
        .filter((r) => typeof r.return_metric_pct === "number")
        .sort(
          (a, b) =>
            (b.return_metric_pct ?? -Infinity) -
            (a.return_metric_pct ?? -Infinity)
        )[0] ?? null;

    const bestCompositeRow =
      suiteRuns
        .filter((r) => typeof r.defense_ready_score === "number")
        .sort(
          (a, b) =>
            (b.defense_ready_score ?? -Infinity) -
            (a.defense_ready_score ?? -Infinity)
        )[0] ?? null;

    const bestSharpeRow =
      suiteRuns
        .filter((r) => typeof r.sharpe === "number")
        .sort((a, b) => (b.sharpe ?? -Infinity) - (a.sharpe ?? -Infinity))[0] ??
      null;

    const maxTickers = suiteRuns.reduce(
      (acc, row) => Math.max(acc, row.n_suite_tickers || 0),
      0
    );

    const medianSharpe = (() => {
      const values = suiteRuns
        .map((row) => row.sharpe)
        .filter((v): v is number => typeof v === "number")
        .sort((a, b) => a - b);

      if (!values.length) return null;
      const mid = Math.floor(values.length / 2);
      return values.length % 2 === 0
        ? (values[mid - 1] + values[mid]) / 2
        : values[mid];
    })();

    const configs = Array.from(new Set(suiteRuns.map((r) => r.config))).filter(
      Boolean
    );
    const stages = Array.from(new Set(suiteRuns.map((r) => r.stage))).filter(
      Boolean
    );
    const uniqueTickers = Array.from(
      new Set(tickerRows.map((r) => r.ticker))
    ).filter(Boolean);

    const okTickerRows = tickerRows.filter(
      (r) => (r.status ?? "").toLowerCase() === "ok"
    ).length;

    const minPValue = (() => {
      const values = suiteRuns
        .map((r) => r.p_value_one_sided)
        .filter((v): v is number => typeof v === "number");
      if (!values.length) return null;
      return Math.min(...values);
    })();

    return {
      runCount,
      bestReturnRow,
      bestCompositeRow,
      bestSharpeRow,
      maxTickers,
      medianSharpe,
      configs,
      stages,
      uniqueTickers,
      okTickerRows,
      minPValue,
    };
  }, [suiteRuns, tickerRows]);

  return (
    <div className="page">
      <section className="hero hero--premium">
        <div className="hero__content">
          <div className="hero__eyebrow">System overview</div>
          <h1 className="hero__title">Analytical Snapshot Overview</h1>
          <p className="hero__description">
            This dashboard summarizes precomputed multi-ticker experiment results,
            compares configuration-level performance, and provides a compact view of
            return, risk, and statistical diagnostics within the current research
            snapshot.
          </p>

          <div className="hero__chips">
            <span className="hero-chip">M8 true multi</span>
            <span className="hero-chip">Curated universe</span>
            <span className="hero-chip">Offline computation</span>
            <span className="hero-chip">Analytical dashboard</span>
          </div>
        </div>

        <div className="hero__sidecard hero__sidecard--premium">
          <div className="hero__sidecard-label">System snapshot</div>
          <div className="hero__sidecard-grid">
            <div>
              <div className="hero__metric-label">Experiment runs</div>
              <div className="hero__metric-value">{stats.runCount}</div>
            </div>
            <div>
              <div className="hero__metric-label">Universe size</div>
              <div className="hero__metric-value">{stats.maxTickers}</div>
            </div>
            <div>
              <div className="hero__metric-label">Best return</div>
              <div className="hero__metric-value">
                {fmt(stats.bestReturnRow?.return_metric_pct)}%
              </div>
            </div>
            <div>
              <div className="hero__metric-label">Median Sharpe</div>
              <div className="hero__metric-value">{fmt(stats.medianSharpe, 3)}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="snapshot-strip">
        <div className="snapshot-card">
          <div className="snapshot-card__label">Loaded configurations</div>
          <div className="snapshot-card__value">{stats.configs.length}</div>
          <div className="snapshot-card__meta">{stats.configs.join(", ") || "—"}</div>
        </div>

        <div className="snapshot-card">
          <div className="snapshot-card__label">Stages present</div>
          <div className="snapshot-card__value">{stats.stages.length}</div>
          <div className="snapshot-card__meta">{stats.stages.join(", ") || "—"}</div>
        </div>

        <div className="snapshot-card">
          <div className="snapshot-card__label">Instrument diagnostics</div>
          <div className="snapshot-card__value">{stats.uniqueTickers.length}</div>
          <div className="snapshot-card__meta">
            {stats.okTickerRows} valid rows across ticker-level outputs
          </div>
        </div>

        <div className="snapshot-card">
          <div className="snapshot-card__label">Best composite score</div>
          <div className="snapshot-card__value">
            {stats.bestCompositeRow?.config ?? "—"}
          </div>
          <div className="snapshot-card__meta">
            Score {fmt(stats.bestCompositeRow?.defense_ready_score, 3)} • p-value{" "}
            {fmt(stats.bestCompositeRow?.p_value_one_sided, 4)}
          </div>
        </div>
      </section>

      <section className="dataset-panel">
        <div className="dataset-panel__header">
          <div>
            <div className="section-label">Dataset metadata</div>
            <h2 className="section-title">Curated universe snapshot</h2>
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

        <div className="dataset-panel__footer">
          <div className="dataset-panel__meta">
            Output root: {manifest?.output_root ?? "not available"}
          </div>
          <div className="dataset-panel__meta">
            Missing files: {manifest?.missing_files_count ?? "—"}
          </div>
        </div>
      </section>

      {loading ? <div className="empty-state">Loading analytical snapshot…</div> : null}

      <div className="kpi-grid">
        <KpiCard
          label="Experiment runs"
          value={String(stats.runCount)}
          hint="Loaded from suite-level index"
          accent="blue"
        />
        <KpiCard
          label="Best return %"
          value={fmt(stats.bestReturnRow?.return_metric_pct)}
          hint="Top configuration by total return"
          accent="cyan"
        />
        <KpiCard
          label="Best composite score"
          value={fmt(stats.bestCompositeRow?.defense_ready_score, 3)}
          hint="Internal ranking metric"
          accent="amber"
        />
        <KpiCard
          label="Max universe size"
          value={String(stats.maxTickers)}
          hint="Instruments inside one suite run"
          accent="blue"
        />
      </div>

      <section className="insight-banner">
        <div className="insight-pill">
          <div className="insight-pill__label">Best return configuration</div>
          <div className="insight-pill__value">
            {stats.bestReturnRow?.config ?? "—"}
          </div>
        </div>
        <div className="insight-pill">
          <div className="insight-pill__label">Best Sharpe configuration</div>
          <div className="insight-pill__value">
            {stats.bestSharpeRow?.config ?? "—"}
          </div>
        </div>
        <div className="insight-pill">
          <div className="insight-pill__label">Minimum p-value</div>
          <div className="insight-pill__value">{fmt(stats.minPValue, 4)}</div>
        </div>
        <div className="insight-pill insight-pill--warning">
          <div className="insight-pill__label">Statistical interpretation</div>
          <div className="insight-pill__value">
            {typeof stats.minPValue === "number" && stats.minPValue <= 0.1
              ? "Some comparative evidence is present"
              : "No strong superiority evidence in the current snapshot"}
          </div>
        </div>
      </section>

      <div className="chart-grid chart-grid--triple">
        <SuiteReturnChart rows={suiteRuns} />
        <SuiteRiskChart rows={suiteRuns} />
        <ReturnDrawdownScatterChart rows={suiteRuns} />
      </div>

      <div className="intelligence-grid intelligence-grid--overview">
        <section className="terminal-card terminal-card--featured">
          <div className="section-label">System positioning</div>
          <h2 className="section-title">Analytical interface scope</h2>
          <p className="section-text">
            ThothMind separates heavy market computation from the interface layer.
            The backend performs batch calculations and generates structured
            artifacts, while the frontend focuses on comparison, interpretation,
            and transparent presentation of the resulting analytical outputs.
          </p>

          <div className="research-annotation-grid">
            <div className="research-annotation">
              <div className="research-annotation__label">Computation layer</div>
              <div className="research-annotation__value">
                Offline experiment pipeline
              </div>
              <div className="research-annotation__text">
                Forecasting, simulation, and metric aggregation are precomputed in
                Python and exported as suite-level and ticker-level artifacts.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">Presentation layer</div>
              <div className="research-annotation__value">
                Comparative analytical interface
              </div>
              <div className="research-annotation__text">
                The UI is designed for structured inspection of saved outputs rather
                than live model retraining or ad hoc computation during a session.
              </div>
            </div>

            <div className="research-annotation">
              <div className="research-annotation__label">Analytical scope</div>
              <div className="research-annotation__value">
                Configuration and instrument diagnostics
              </div>
              <div className="research-annotation__text">
                The interface combines aggregate configuration-level comparisons with
                instrument-level diagnostics inside a stable demonstration workflow.
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Return ranking</div>
          <h2 className="section-title">Top return configurations</h2>
          <div className="mini-list">
            {topReturn.length === 0 ? (
              <div className="empty-state">No top-by-return snapshot is available.</div>
            ) : (
              topReturn.slice(0, 5).map((row, idx) => (
                <div className="mini-list__item" key={`${row.config}-${idx}`}>
                  <div>
                    <div className="mini-list__title">{row.config}</div>
                    <div className="mini-list__meta">
                      {row.ticker} • {row.n_suite_tickers ?? 0} instruments
                    </div>
                  </div>
                  <div className="mini-list__value">{fmt(row.return_metric_pct)}%</div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Composite ranking</div>
          <h2 className="section-title">Top composite score configurations</h2>
          <div className="mini-list">
            {topComposite.length === 0 ? (
              <div className="empty-state">No composite ranking snapshot is available.</div>
            ) : (
              topComposite.slice(0, 5).map((row, idx) => (
                <div className="mini-list__item" key={`${row.config}-${idx}`}>
                  <div>
                    <div className="mini-list__title">{row.config}</div>
                    <div className="mini-list__meta">
                      {row.ticker} • p-value {fmt(row.p_value_one_sided, 4)}
                    </div>
                  </div>
                  <div className="mini-list__value">
                    {fmt(row.defense_ready_score, 3)}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}