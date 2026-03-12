import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { SuiteRun } from "../../shared/types/api";

type Props = {
  suiteRuns: SuiteRun[];
};

function shortConfigName(config: string): string {
  return config
    .replace(".yaml", "")
    .replace("exp_", "")
    .replace("demo_", "")
    .replace("multiticker_suite_", "")
    .replace("multiticker_suite", "base");
}

function fmt(value: unknown, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
}

export default function CommissionOverviewCharts({ suiteRuns }: Props) {
  const rows = suiteRuns.map((row) => ({
    ...row,
    short: shortConfigName(row.config),
    absDd: Math.abs(row.max_drawdown_pct ?? 0),
    bubble: Math.max(((row.defense_ready_score ?? 0) + 5) * 3, 80),
  }));

  const benchmarkGapRows = suiteRuns.map((row) => ({
    short: shortConfigName(row.config),
    config: row.config,
    gap: row.actual_rel_return_pct ?? 0,
  }));

  const diagnosticsRows = suiteRuns.map((row) => ({
    config: row.config,
    short: shortConfigName(row.config),
    pValue: row.p_value_one_sided ?? null,
    dd: Math.abs(row.max_drawdown_pct ?? 0),
    sharpe: row.sharpe ?? null,
  }));

  return (
    <div className="page" style={{ gap: 18 }}>
      <section className="terminal-card terminal-card--featured">
        <div className="section-label">Extended configuration analytics</div>
        <h2 className="section-title">Comparative configuration diagnostics</h2>
        <p className="section-text">
          These additional charts extend the suite registry with a compact comparative
          view of return, risk-adjusted quality, benchmark-relative performance, and
          statistical diagnostics for the currently loaded experiment configurations.
        </p>
      </section>

      <div className="chart-grid chart-grid--triple">
        <div className="chart-card">
          <div className="section-label">Performance map</div>
          <h2 className="section-title">Return vs Sharpe</h2>
          <div className="chart-card__body">
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart margin={{ top: 12, right: 12, bottom: 8, left: 8 }}>
                <CartesianGrid stroke="rgba(155,168,199,0.12)" />
                <XAxis
                  type="number"
                  dataKey="sharpe"
                  name="Sharpe"
                  tick={{ fill: "#9ba8c7", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="number"
                  dataKey="return_metric_pct"
                  name="Return"
                  tick={{ fill: "#9ba8c7", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <ZAxis type="number" dataKey="bubble" range={[120, 420]} />
                <Tooltip
                  cursor={{ strokeDasharray: "4 4", stroke: "rgba(255,255,255,0.18)" }}
                  contentStyle={{
                    background: "rgba(10,17,31,0.95)",
                    border: "1px solid rgba(114,138,190,0.18)",
                    borderRadius: 14,
                    color: "#f4f7ff",
                  }}
                  formatter={(value, name) => {
                    if (String(name) === "Return") return [`${fmt(value)}%`, "Return"];
                    return [fmt(value, 4), "Sharpe"];
                  }}
                  labelFormatter={(_, payload) => String(payload?.[0]?.payload?.config ?? "")}
                />
                <Scatter data={rows} fill="#70a5ff" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="section-label">Benchmark comparison</div>
          <h2 className="section-title">Excess return vs benchmark</h2>
          <div className="chart-card__body">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={benchmarkGapRows} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="rgba(155,168,199,0.12)" vertical={false} />
                <XAxis
                  dataKey="short"
                  tick={{ fill: "#9ba8c7", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#9ba8c7", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(10,17,31,0.95)",
                    border: "1px solid rgba(114,138,190,0.18)",
                    borderRadius: 14,
                    color: "#f4f7ff",
                  }}
                  formatter={(value) => [`${fmt(value)}%`, "Benchmark gap"]}
                  labelFormatter={(_, payload) => String(payload?.[0]?.payload?.config ?? "")}
                />
                <Bar dataKey="gap" fill="#71e7dc" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="section-label">Diagnostics summary</div>
          <h2 className="section-title">p-value and drawdown overview</h2>
          <div className="research-annotation-grid" style={{ marginTop: 12 }}>
            {diagnosticsRows.map((row) => (
              <div className="research-annotation" key={row.config}>
                <div className="research-annotation__label">{row.short}</div>
                <div className="research-annotation__text">
                  p-value {fmt(row.pValue, 4)} • |drawdown| {fmt(row.dd)}% • Sharpe {fmt(row.sharpe, 4)}
                </div>
                <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
                  <div>
                    <div className="research-annotation__label" style={{ marginBottom: 6 }}>
                      p-value scale
                    </div>
                    <div style={{ height: 8, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${Math.max(3, Math.min(100, ((row.pValue ?? 0) / 1) * 100))}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: "linear-gradient(90deg, rgba(113,231,220,0.95), rgba(112,165,255,0.95))",
                        }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="research-annotation__label" style={{ marginBottom: 6 }}>
                      absolute drawdown scale
                    </div>
                    <div style={{ height: 8, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${Math.max(3, Math.min(100, (row.dd / 60) * 100))}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: "linear-gradient(90deg, rgba(255,191,117,0.95), rgba(255,154,154,0.95))",
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}