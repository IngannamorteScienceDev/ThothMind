import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type SuiteRunRow = {
  config: string;
  return_metric_pct?: number;
  sharpe?: number;
  max_drawdown_pct?: number;
  p_value_one_sided?: number;
  actual_rel_return_pct?: number;
  defense_ready_score?: number;
};

type Props = {
  suiteRuns: SuiteRunRow[];
};

function shortConfigName(config: string): string {
  return config
    .replace(".yaml", "")
    .replace("exp_", "")
    .replace("demo_", "")
    .replace("multiticker_suite_", "")
    .replace("multiticker_suite", "base");
}

function fmt(value?: number, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return Number(value).toFixed(digits);
}

const palette = ["#7dd3fc", "#67e8f9", "#a78bfa", "#fbbf24", "#34d399", "#fb7185"];

export function CommissionOverviewCharts({ suiteRuns }: Props) {
  const rows = [...suiteRuns];

  const scatterRows = rows.map((row, idx) => ({
    ...row,
    short: shortConfigName(row.config),
    color: palette[idx % palette.length],
    absDd: Math.abs(row.max_drawdown_pct ?? 0),
  }));

  const benchmarkGapRows = rows.map((row) => ({
    short: shortConfigName(row.config),
    gap: row.actual_rel_return_pct ?? 0,
  }));

  const pValueRows = rows.map((row) => ({
    short: shortConfigName(row.config),
    pValue: row.p_value_one_sided ?? 0,
    dd: Math.abs(row.max_drawdown_pct ?? 0),
  }));

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <section className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-cyan-300/90">
          performance map
        </div>
        <h3 className="mb-4 text-2xl font-semibold text-white">Return vs Sharpe</h3>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 16, right: 20, bottom: 16, left: 6 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.10)" />
              <XAxis
                type="number"
                dataKey="sharpe"
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
                name="Sharpe"
              />
              <YAxis
                type="number"
                dataKey="return_metric_pct"
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
                name="Return %"
              />
              <Tooltip
                cursor={{ strokeDasharray: "4 4" }}
                contentStyle={{
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(2,6,23,0.95)",
                }}
                formatter={(value: number, name: string) => [
                  fmt(value),
                  name === "return_metric_pct" ? "Return %" : "Sharpe",
                ]}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.config ?? ""}
              />
              <Scatter data={scatterRows}>
                {scatterRows.map((entry, index) => (
                  <Cell key={`${entry.config}-${index}`} fill={entry.color} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-cyan-300/90">
          benchmark comparison
        </div>
        <h3 className="mb-4 text-2xl font-semibold text-white">Excess return vs benchmark</h3>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={benchmarkGapRows} margin={{ top: 16, right: 12, left: 0, bottom: 16 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.10)" vertical={false} />
              <XAxis
                dataKey="short"
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
              />
              <YAxis
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(2,6,23,0.95)",
                }}
                formatter={(value: number) => [fmt(value), "Excess return %"]}
              />
              <Bar dataKey="gap" radius={[10, 10, 0, 0]} fill="url(#gapGradient)">
                <LabelList dataKey="gap" position="top" formatter={(v: number) => fmt(v)} />
              </Bar>
              <defs>
                <linearGradient id="gapGradient" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#67e8f9" />
                  <stop offset="100%" stopColor="#2563eb" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-cyan-300/90">
          statistical diagnostics
        </div>
        <h3 className="mb-4 text-2xl font-semibold text-white">p-value and drawdown</h3>
        <div className="space-y-4">
          {pValueRows.map((row, idx) => (
            <div key={row.short} className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm font-medium text-slate-200">{row.short}</div>
                <div className="text-xs text-slate-400">
                  p={fmt(row.pValue, 4)} · DD={fmt(row.dd)}%
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="mb-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                    p-value
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.max(2, Math.min(100, row.pValue * 100))}%`,
                        background: palette[idx % palette.length],
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                    |drawdown|
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-amber-300"
                      style={{
                        width: `${Math.max(2, Math.min(100, (row.dd / 50) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}