import { useEffect, useState } from "react";
import type { SuiteRun } from "../shared/types/api";
import { loadSuiteRuns } from "../services/dataLoader";
import { adaptSuiteRuns } from "../services/adapters";
import SuiteRunsTable from "../widgets/tables/SuiteRunsTable";

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

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Suite Runs</h1>
          <p>Suite-level batch results produced by M8 true multi-ticker execution.</p>
        </div>
      </div>

      {loading ? (
        <div className="empty-state">Loading suite runs…</div>
      ) : rows.length === 0 ? (
        <div className="empty-state">No suite-level results found in public/data/index/all_results_index.json</div>
      ) : (
        <SuiteRunsTable rows={rows} />
      )}
    </div>
  );
}
