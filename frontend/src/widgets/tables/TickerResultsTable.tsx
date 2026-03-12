import type { SuiteTickerResult } from "../../shared/types/api";

type Props = {
  rows: SuiteTickerResult[];
};

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

function statusTone(value: string | undefined) {
  const v = (value ?? "").toLowerCase();
  if (v === "ok") return "badge badge--emerald";
  if (v === "err" || v === "error") return "badge badge--amber";
  return "badge";
}

function pValueTone(value: number | null | undefined) {
  if (typeof value !== "number") return "";
  if (value <= 0.1) return "tone-positive";
  if (value <= 0.25) return "tone-calm";
  return "tone-warn";
}

export default function TickerResultsTable({ rows }: Props) {
  return (
    <div className="table-card table-card--terminal">
      <div className="table-card__header">
        <div>
          <div className="section-label">Instrument diagnostics</div>
          <div className="table-card__title">Per-instrument analytical output</div>
        </div>
        <div className="table-card__meta">{rows.length} rows visible</div>
      </div>

      <div className="table-wrap">
        <table className="tm-table tm-table--terminal">
          <thead>
            <tr>
              <th>Configuration</th>
              <th>Instrument</th>
              <th>Status</th>
              <th>Return %</th>
              <th>Sharpe</th>
              <th>Max Drawdown %</th>
              <th>Benchmark Gap %</th>
              <th>p-value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.config}-${row.ticker}-${idx}`}>
                <td>
                  <div className="cell-primary">{row.config}</div>
                </td>
                <td>
                  <span className="badge badge--blue">{row.ticker}</span>
                </td>
                <td>
                  <span className={statusTone(row.status)}>{row.status ?? "—"}</span>
                </td>
                <td className="num-cell">{fmt(row.strat_total_return)}</td>
                <td className="num-cell">{fmt(row.strat_sharpe, 4)}</td>
                <td className="num-cell">{fmt(row.strat_max_drawdown)}</td>
                <td className="num-cell">{fmt(row.actual_rel_return)}</td>
                <td className={`num-cell ${pValueTone(row.p_value_one_sided ?? null)}`}>
                  {fmt(row.p_value_one_sided, 4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}