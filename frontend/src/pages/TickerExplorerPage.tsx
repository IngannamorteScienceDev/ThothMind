import { useEffect, useMemo, useState } from "react";
import type { SuiteTickerResult } from "../shared/types/api";
import { loadSuiteTickerResults } from "../services/dataLoader";
import { adaptSuiteTickerResults } from "../services/adapters";
import TickerResultsTable from "../widgets/tables/TickerResultsTable";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function TickerExplorerPage() {
  const [rows, setRows] = useState<SuiteTickerResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [configFilter, setConfigFilter] = useState("ALL");

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      const raw = await loadSuiteTickerResults();
      setRows(adaptSuiteTickerResults(raw));
      setLoading(false);
    }

    bootstrap();
  }, []);

  const configOptions = useMemo(() => {
    return ["ALL", ...Array.from(new Set(rows.map((r) => r.config))).sort()];
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return rows.filter((row) => {
      const queryOk =
        !q ||
        row.ticker.toLowerCase().includes(q) ||
        row.config.toLowerCase().includes(q);

      const configOk = configFilter === "ALL" || row.config === configFilter;

      return queryOk && configOk;
    });
  }, [rows, query, configFilter]);

  const stats = useMemo(() => {
    const uniqueTickers = new Set(filtered.map((r) => r.ticker)).size;
    const uniqueConfigs = new Set(filtered.map((r) => r.config)).size;

    const avgSharpeValues = filtered
      .map((r) => r.strat_sharpe)
      .filter((v): v is number => typeof v === "number");

    const avgSharpe =
      avgSharpeValues.length > 0
        ? avgSharpeValues.reduce((a, b) => a + b, 0) / avgSharpeValues.length
        : null;

    const bestTicker =
      filtered
        .filter((r) => typeof r.strat_total_return === "number")
        .sort(
          (a, b) =>
            (b.strat_total_return ?? -Infinity) - (a.strat_total_return ?? -Infinity)
        )[0] ?? null;

    return {
      uniqueTickers,
      uniqueConfigs,
      avgSharpe,
      bestTicker,
    };
  }, [filtered]);

  return (
    <div className="page">
      <section className="section-hero">
        <div className="section-hero__content">
          <div className="section-label">Instrument diagnostics</div>
          <h1 className="section-hero__title">Ticker Explorer</h1>
          <p className="section-hero__text">
            Explore per-ticker outputs inside multi-ticker suite runs. Use this view to compare
            instruments, inspect configuration sensitivity, and demonstrate that the system stores
            interpretable diagnostics beyond aggregate suite-level metrics.
          </p>
        </div>

        <div className="section-hero__stats">
          <div className="mini-stat">
            <div className="mini-stat__label">Rows</div>
            <div className="mini-stat__value">{filtered.length}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Tickers</div>
            <div className="mini-stat__value">{stats.uniqueTickers}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Configs</div>
            <div className="mini-stat__value">{stats.uniqueConfigs}</div>
          </div>
        </div>
      </section>

      <div className="metrics-strip">
        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Average sharpe</div>
          <div className="metrics-strip__title">{fmt(stats.avgSharpe, 4)}</div>
          <div className="metrics-strip__meta">
            Calculated over currently filtered per-ticker rows
          </div>
        </div>

        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Best visible ticker</div>
          <div className="metrics-strip__title">
            {stats.bestTicker?.ticker ?? "—"}
          </div>
          <div className="metrics-strip__meta">
            {stats.bestTicker?.config ?? "—"} • Return{" "}
            {fmt(stats.bestTicker?.strat_total_return)}
          </div>
        </div>
      </div>

      <div className="toolbar toolbar--terminal">
        <input
          className="search-input"
          placeholder="Filter by ticker or config…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <select
          className="select-input"
          value={configFilter}
          onChange={(e) => setConfigFilter(e.target.value)}
        >
          {configOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="empty-state">Loading per-ticker results…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">No per-ticker rows found for current filters.</div>
      ) : (
        <TickerResultsTable rows={filtered} />
      )}
    </div>
  );
}