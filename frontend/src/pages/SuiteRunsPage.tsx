import { useEffect, useMemo, useState } from "react";
import type { SuiteRun } from "../shared/types/api";
import { loadSuiteRuns } from "../services/dataLoader";
import { adaptSuiteRuns } from "../services/adapters";
import SuiteRunsTable from "../widgets/tables/SuiteRunsTable";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function SuiteRunsPage() {
  const [rows, setRows] = useState<SuiteRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      const raw = await loadSuiteRuns();
      setRows(adaptSuiteRuns(raw));
      setLoading(false);
    }

    bootstrap();
  }, []);

  const stats = useMemo(() => {
    const configs = new Set(rows.map((r) => r.config)).size;
    const stages = new Set(rows.map((r) => r.stage)).size;
    const maxUniverse = rows.reduce(
      (acc, row) => Math.max(acc, row.n_suite_tickers || 0),
      0
    );

    const bestReturnRow =
      rows
        .filter((r) => typeof r.return_metric_pct === "number")
        .sort(
          (a, b) =>
            (b.return_metric_pct ?? -Infinity) -
            (a.return_metric_pct ?? -Infinity)
        )[0] ?? null;

    const bestCompositeRow =
      rows
        .filter((r) => typeof r.defense_ready_score === "number")
        .sort(
          (a, b) =>
            (b.defense_ready_score ?? -Infinity) -
            (a.defense_ready_score ?? -Infinity)
        )[0] ?? null;

    return {
      configs,
      stages,
      maxUniverse,
      bestReturnRow,
      bestCompositeRow,
    };
  }, [rows]);

  return (
    <div className="page">
      <section className="section-hero">
        <div className="section-hero__content">
          <div className="section-label">Experiment registry</div>
          <h1 className="section-hero__title">Experiment Registry</h1>
          <p className="section-hero__text">
            Compare suite-level results across curated-universe configurations,
            forecasting stages, and ranking outputs. This section acts as the main
            registry of saved experiment runs inside the current analytical
            snapshot.
          </p>
        </div>

        <div className="section-hero__stats">
          <div className="mini-stat">
            <div className="mini-stat__label">Configs</div>
            <div className="mini-stat__value">{stats.configs}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Stages</div>
            <div className="mini-stat__value">{stats.stages}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Universe</div>
            <div className="mini-stat__value">{stats.maxUniverse}</div>
          </div>
        </div>
      </section>

      <div className="metrics-strip">
        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Best return configuration</div>
          <div className="metrics-strip__title">
            {stats.bestReturnRow?.config ?? "—"}
          </div>
          <div className="metrics-strip__meta">
            Return {fmt(stats.bestReturnRow?.return_metric_pct)}% • Sharpe{" "}
            {fmt(stats.bestReturnRow?.sharpe, 4)}
          </div>
        </div>

        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Best composite score</div>
          <div className="metrics-strip__title">
            {stats.bestCompositeRow?.config ?? "—"}
          </div>
          <div className="metrics-strip__meta">
            Score {fmt(stats.bestCompositeRow?.defense_ready_score, 3)} • p-value{" "}
            {fmt(stats.bestCompositeRow?.p_value_one_sided, 4)}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="empty-state">Loading experiment registry…</div>
      ) : rows.length === 0 ? (
        <div className="empty-state">
          No suite-level results were found in the published snapshot.
        </div>
      ) : (
        <SuiteRunsTable rows={rows} />
      )}
    </div>
  );
}