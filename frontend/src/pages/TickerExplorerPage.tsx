import { useEffect, useMemo, useState } from "react";
import type { SuiteTickerResult } from "../shared/types/api";
import { loadSuiteTickerResults } from "../services/dataLoader";
import { adaptSuiteTickerResults } from "../services/adapters";
import TickerResultsTable from "../widgets/tables/TickerResultsTable";
import TickerConfigComparisonChart from "../widgets/charts/TickerConfigComparisonChart";
import TickerReturnDistributionChart from "../widgets/charts/TickerReturnDistributionChart";

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function TickerExplorerPage() {
  const [rows, setRows] = useState<SuiteTickerResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [configFilter, setConfigFilter] = useState("ALL");
  const [tickerFilter, setTickerFilter] = useState("ALL");

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

  const tickerOptions = useMemo(() => {
    return ["ALL", ...Array.from(new Set(rows.map((r) => r.ticker))).sort()];
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return rows.filter((row) => {
      const queryOk =
        !q ||
        row.ticker.toLowerCase().includes(q) ||
        row.config.toLowerCase().includes(q);

      const configOk = configFilter === "ALL" || row.config === configFilter;
      const tickerOk = tickerFilter === "ALL" || row.ticker === tickerFilter;

      return queryOk && configOk && tickerOk;
    });
  }, [rows, query, configFilter, tickerFilter]);

  const comparisonTicker = useMemo(() => {
    if (tickerFilter !== "ALL") return tickerFilter;
    const first = filtered[0]?.ticker;
    return first ?? "";
  }, [filtered, tickerFilter]);

  const comparisonRows = useMemo(() => {
    if (!comparisonTicker) return [];
    return rows.filter((row) => row.ticker === comparisonTicker);
  }, [rows, comparisonTicker]);

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
            (b.strat_total_return ?? -Infinity) -
            (a.strat_total_return ?? -Infinity)
        )[0] ?? null;

    const worstTicker =
      filtered
        .filter((r) => typeof r.strat_total_return === "number")
        .sort(
          (a, b) =>
            (a.strat_total_return ?? Infinity) -
            (b.strat_total_return ?? Infinity)
        )[0] ?? null;

    return {
      uniqueTickers,
      uniqueConfigs,
      avgSharpe,
      bestTicker,
      worstTicker,
    };
  }, [filtered]);

  return (
    <div className="page">
      <section className="section-hero">
        <div className="section-hero__content">
          <div className="section-label">Instrument analytics</div>
          <h1 className="section-hero__title">Instrument Analytics</h1>
          <p className="section-hero__text">
            Explore ticker-level results generated inside multi-ticker suite runs.
            This screen is intended for instrument comparison, configuration
            sensitivity analysis, and interpretation of per-instrument performance
            dispersion beyond aggregate suite-level metrics.
          </p>
        </div>

        <div className="section-hero__stats">
          <div className="mini-stat">
            <div className="mini-stat__label">Rows</div>
            <div className="mini-stat__value">{filtered.length}</div>
          </div>
          <div className="mini-stat">
            <div className="mini-stat__label">Instruments</div>
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
          <div className="metrics-strip__label">Average Sharpe</div>
          <div className="metrics-strip__title">{fmt(stats.avgSharpe, 4)}</div>
          <div className="metrics-strip__meta">
            Calculated over the currently filtered ticker-level rows
          </div>
        </div>

        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Best visible instrument</div>
          <div className="metrics-strip__title">
            {stats.bestTicker?.ticker ?? "—"}
          </div>
          <div className="metrics-strip__meta">
            {stats.bestTicker?.config ?? "—"} • Return{" "}
            {fmt(stats.bestTicker?.strat_total_return)}%
          </div>
        </div>

        <div className="metrics-strip__card">
          <div className="metrics-strip__label">Weakest visible instrument</div>
          <div className="metrics-strip__title">
            {stats.worstTicker?.ticker ?? "—"}
          </div>
          <div className="metrics-strip__meta">
            {stats.worstTicker?.config ?? "—"} • Return{" "}
            {fmt(stats.worstTicker?.strat_total_return)}%
          </div>
        </div>
      </div>

      <div className="toolbar toolbar--terminal">
        <input
          className="search-input"
          placeholder="Filter by instrument or configuration…"
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

        <select
          className="select-input"
          value={tickerFilter}
          onChange={(e) => setTickerFilter(e.target.value)}
        >
          {tickerOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      <div className="chart-grid">
        {comparisonTicker ? (
          <TickerConfigComparisonChart rows={comparisonRows} ticker={comparisonTicker} />
        ) : (
          <div className="empty-state">
            No instrument is available for configuration comparison.
          </div>
        )}

        <TickerReturnDistributionChart rows={filtered} />
      </div>

      <div className="insight-grid">
        <section className="terminal-card">
          <div className="section-label">Analytical note</div>
          <h2 className="section-title">Configuration sensitivity</h2>
          <p className="section-text">
            The comparison chart shows how the same instrument behaves under
            different suite configurations. This is useful for demonstrating that
            the system stores interpretable instrument-level diagnostics rather than
            only a single aggregate ranking.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Analytical note</div>
          <h2 className="section-title">Distribution interpretation</h2>
          <p className="section-text">
            The return distribution chart helps assess whether visible instrument
            results are concentrated in a limited subset or spread more broadly
            across the filtered universe.
          </p>
        </section>

        <section className="terminal-card">
          <div className="section-label">Risk note</div>
          <h2 className="section-title">Current weakest visible instrument</h2>
          <p className="section-text">
            {(stats.worstTicker?.ticker ?? "—")} under{" "}
            {(stats.worstTicker?.config ?? "—")} currently shows return{" "}
            {fmt(stats.worstTicker?.strat_total_return)}% and drawdown{" "}
            {fmt(stats.worstTicker?.strat_max_drawdown)}%.
          </p>
        </section>
      </div>

      {loading ? (
        <div className="empty-state">Loading instrument-level results…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          No ticker-level rows found for the current filters.
        </div>
      ) : (
        <TickerResultsTable rows={filtered} />
      )}
    </div>
  );
}