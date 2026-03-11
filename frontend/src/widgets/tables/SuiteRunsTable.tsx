import type { SuiteRun } from "../../shared/types/api";

type Props = {
  rows: SuiteRun[];
};

function fmt(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

function scoreTone(value: number | null | undefined) {
  if (typeof value !== "number") return "tone-neutral";
  if (value >= 70) return "tone-positive";
  if (value >= 45) return "tone-calm";
  return "tone-warn";
}

function pValueTone(value: number | null | undefined) {
  if (typeof value !== "number") return "tone-neutral";
  if (value <= 0.1) return "tone-positive";
  if (value <= 0.25) return "tone-calm";
  return "tone-warn";
}

export default function SuiteRunsTable({ rows }: Props) {
  return (
    <div className="table-card table-card--terminal">
      <div className="table-card__header">
        <div>
          <div className="section-label">Suite registry</div>
          <div className="table-card__title">Multi-ticker experiment catalog</div>
        </div>
        <div className="table-card__meta">{rows.length} suite runs loaded</div>
      </div>

      <div className="table-wrap">
        <table className="tm-table tm-table--terminal">
          <thead>
            <tr>
              <th>Config</th>
              <th>Ticker</th>
              <th>Stage</th>
              <th>Mode</th>
              <th>Universe</th>
              <th>Return %</th>
              <th>Sharpe</th>
              <th>Max DD %</th>
              <th>p-value</th>
              <th>Defense</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${row.config}-${idx}`}>
                <td>
                  <div className="cell-primary">{row.config}</div>
                </td>
                <td>
                  <span className="badge badge--blue">{row.ticker}</span>
                </td>
                <td>
                  <span className="badge badge--cyan">{row.stage}</span>
                </td>
                <td>{row.suite_mode}</td>
                <td>{row.n_suite_tickers}</td>
                <td className="num-cell">{fmt(row.return_metric_pct)}</td>
                <td className="num-cell">{fmt(row.sharpe, 4)}</td>
                <td className="num-cell">{fmt(row.max_drawdown_pct)}</td>
                <td className={`num-cell ${pValueTone(row.p_value_one_sided)}`}>
                  {fmt(row.p_value_one_sided, 4)}
                </td>
                <td className={`num-cell ${scoreTone(row.defense_ready_score)}`}>
                  {fmt(row.defense_ready_score, 3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}