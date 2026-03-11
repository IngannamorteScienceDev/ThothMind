import { useEffect, useMemo, useState } from "react";
import type { SuiteTickerResult } from "../shared/types/api";
import { loadSuiteTickerResults } from "../services/dataLoader";
import { adaptSuiteTickerResults } from "../services/adapters";
import TickerResultsTable from "../widgets/tables/TickerResultsTable";

export default function TickerExplorerPage() {
  const [rows, setRows] = useState<SuiteTickerResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      const raw = await loadSuiteTickerResults();
      setRows(adaptSuiteTickerResults(raw));
      setLoading(false);
    }

    bootstrap();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (row) =>
        row.ticker.toLowerCase().includes(q) ||
        row.config.toLowerCase().includes(q)
    );
  }, [rows, query]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Ticker Explorer</h1>
          <p>Per-ticker results inside suite-level M8 runs.</p>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Filter by ticker or config…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="empty-state">Loading per-ticker results…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">No per-ticker rows found.</div>
      ) : (
        <TickerResultsTable rows={filtered} />
      )}
    </div>
  );
}
