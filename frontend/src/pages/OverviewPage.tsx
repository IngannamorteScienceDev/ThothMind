import { useEffect, useMemo, useState } from "react";
import type { SuiteRun, TopRun } from "../shared/types/api";
import {
  loadSuiteRuns,
  loadTopByReturn,
  loadTopDefenseReady,
} from "../services/dataLoader";
import { adaptSuiteRuns, adaptTopRuns } from "../services/adapters";
import KpiCard from "../widgets/kpi/KpiCard";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function OverviewPage() {
  const [suiteRuns, setSuiteRuns] = useState<SuiteRun[]>([]);
  const [topReturn, setTopReturn] = useState<TopRun[]>([]);
  const [topDefense, setTopDefense] = useState<TopRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);

      const [suiteRaw, topReturnRaw, topDefenseRaw] = await Promise.all([
        loadSuiteRuns(),
        loadTopByReturn(),
        loadTopDefenseReady(),
      ]);

      setSuiteRuns(adaptSuiteRuns(suiteRaw));
      setTopReturn(adaptTopRuns(topReturnRaw));
      setTopDefense(adaptTopRuns(topDefenseRaw));
      setLoading(false);
    }

    bootstrap();
  }, []);

  const stats = useMemo(() => {
    const runCount = suiteRuns.length;

    const bestReturn = suiteRuns.reduce<number | null>((acc, row) => {
      if (row.return_metric_pct == null) return acc;
      if (acc == null || row.return_metric_pct > acc) return row.return_metric_pct;
      return acc;
    }, null);

    const bestDefense = suiteRuns.reduce<number | null>((acc, row) => {
      if (row.defense_ready_score == null) return acc;
      if (acc == null || row.defense_ready_score > acc) return row.defense_ready_score;
      return acc;
    }, null);

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

    return {
      runCount,
      bestReturn,
      bestDefense,
      maxTickers,
      medianSharpe,
    };
  }, [suiteRuns]);

  return (
    <div className="page">
      <section className="hero">
        <div className="hero__content">
          <div className="hero__eyebrow">Quant research interface</div>
          <h1 className="hero__title">ThothMind Research Terminal</h1>
          <p className="hero__description">
            Offline-first analytical environment for evaluating precomputed
            market forecasting experiments, multi-ticker suite runs, and
            comparative investment scenarios.
          </p>

          <div className="hero__chips">
            <span className="hero-chip">M8 true multi</span>
            <span className="hero-chip">Curated universe</span>
            <span className="hero-chip">Precomputed backend</span>
          </div>
        </div>

        <div className="hero__sidecard">
          <div className="hero__sidecard-label">System snapshot</div>
          <div className="hero__sidecard-grid">
            <div>
              <div className="hero__metric-label">Suite runs</div>
              <div className="hero__metric-value">{stats.runCount}</div>
            </div>
            <div>
              <div className="hero__metric-label">Universe size</div>
              <div className="hero__metric-value">{stats.maxTickers}</div>
            </div>
            <div>
              <div className="hero__metric-label">Best return</div>
              <div className="hero__metric-value">{fmt(stats.bestReturn)}%</div>
            </div>
            <div>
              <div className="hero__metric-label">Median sharpe</div>
              <div className="hero__metric-value">{fmt(stats.medianSharpe, 3)}</div>
            </div>
          </div>
        </div>
      </section>

      {loading ? (
        <div className="empty-state">Loading research snapshot…</div>
      ) : null}

      <div className="kpi-grid">
        <KpiCard
          label="Suite runs"
          value={String(stats.runCount)}
          hint="Loaded from suite-level index"
          accent="blue"
        />
        <KpiCard
          label="Best return %"
          value={fmt(stats.bestReturn)}
          hint="Top suite-level result"
          accent="cyan"
        />
        <KpiCard
          label="Best defense score"
          value={fmt(stats.bestDefense, 3)}
          hint="Current ranking metric"
          accent="amber"
        />
        <KpiCard
          label="Max universe size"
          value={String(stats.maxTickers)}
          hint="Tickers inside one suite run"
          accent="blue"
        />
      </div>

      <div className="intelligence-grid">
        <section className="terminal-card terminal-card--featured">
          <div className="section-label">Research summary</div>
          <h2 className="section-title">What this interface shows</h2>
          <p className="section-text">
            ThothMind separates heavy market computation from the visual layer.
            The backend runs batch experiments offline, aggregates suite-level
            and per-ticker results, and the frontend turns those artifacts into
            an interpretable research terminal.
          </p>
          <div className="bullet-grid">
            <div className="bullet-card">
              <div className="bullet-card__title">Suite-level evaluation</div>
              <div className="bullet-card__text">
                Compare configurations such as base, h5, h10, and h20 across a
                curated universe.
              </div>
            </div>
            <div className="bullet-card">
              <div className="bullet-card__title">Per-ticker diagnostics</div>
              <div className="bullet-card__text">
                Inspect instrument-level performance, relative return, drawdown,
                and confidence metrics.
              </div>
            </div>
            <div className="bullet-card">
              <div className="bullet-card__title">Defense-ready presentation</div>
              <div className="bullet-card__text">
                Use precomputed artifacts for a stable and convincing live demo
                during thesis defense.
              </div>
            </div>
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Top suite runs</div>
          <h2 className="section-title">Return leaderboard</h2>
          <div className="mini-list">
            {topReturn.length === 0 ? (
              <div className="empty-state">No top-by-return JSON loaded yet.</div>
            ) : (
              topReturn.slice(0, 5).map((row, idx) => (
                <div className="mini-list__item" key={`${row.config}-${idx}`}>
                  <div>
                    <div className="mini-list__title">{row.config}</div>
                    <div className="mini-list__meta">
                      {row.ticker} • {row.n_suite_tickers ?? 0} tickers
                    </div>
                  </div>
                  <div className="mini-list__value">{fmt(row.return_metric_pct)}%</div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="terminal-card">
          <div className="section-label">Ranking heuristic</div>
          <h2 className="section-title">Defense-ready leaderboard</h2>
          <div className="mini-list">
            {topDefense.length === 0 ? (
              <div className="empty-state">No defense-ready JSON loaded yet.</div>
            ) : (
              topDefense.slice(0, 5).map((row, idx) => (
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