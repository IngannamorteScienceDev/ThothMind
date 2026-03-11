import type { SuiteTickerResult } from "../../shared/types/api";

type Props = {
  rows: SuiteTickerResult[];
};

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function TickerResultsTable({ rows }: Props) {
  return (
    <div className="table-card">
      <div className="table-card__title">Per-ticker suite results</div>
      <div className="table-wrap">
        <table className="tm-table">
          <thead>
            <tr>
              <th>Config</th>
              <th>Ticker</th>
              <th>Status</th>
              <th>Return</th>
              <th>Sharpe</th>
              <th>Max DD</th>
              <th>Actual Rel Return</th>
              <th>p-value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.config}-${row.ticker}-${idx}`}>
                <td>{row.config}</td>
                <td>{row.ticker}</td>
                <td>{row.status ?? "—"}</td>
                <td>{fmt(row.strat_total_return)}</td>
                <td>{fmt(row.strat_sharpe, 4)}</td>
                <td>{fmt(row.strat_max_drawdown)}</td>
                <td>{fmt(row.actual_rel_return)}</td>
                <td>{fmt(row.p_value_one_sided, 4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
