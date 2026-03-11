import type { SuiteRun } from "../../shared/types/api";

type Props = {
  rows: SuiteRun[];
};

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function SuiteRunsTable({ rows }: Props) {
  return (
    <div className="table-card">
      <div className="table-card__title">Suite-level runs</div>
      <div className="table-wrap">
        <table className="tm-table">
          <thead>
            <tr>
              <th>Config</th>
              <th>Ticker</th>
              <th>Stage</th>
              <th>Suite mode</th>
              <th>N tickers</th>
              <th>Return %</th>
              <th>Sharpe</th>
              <th>Max DD %</th>
              <th>p-value</th>
              <th>Defense score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.config}-${idx}`}>
                <td>{row.config}</td>
                <td>{row.ticker}</td>
                <td>{row.stage}</td>
                <td>{row.suite_mode}</td>
                <td>{row.n_suite_tickers}</td>
                <td>{fmt(row.return_metric_pct)}</td>
                <td>{fmt(row.sharpe, 4)}</td>
                <td>{fmt(row.max_drawdown_pct)}</td>
                <td>{fmt(row.p_value_one_sided, 4)}</td>
                <td>{fmt(row.defense_ready_score, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
