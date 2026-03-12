import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = {
  config: string;
  sharpe: number | null;
  max_drawdown_pct: number | null;
};

type Props = {
  rows: Row[];
};

function shortConfigName(value: string) {
  return value
    .replace("exp_", "")
    .replace("multiticker_suite", "suite")
    .replace(".yaml", "");
}

function fmtNumber(value: unknown, digits = 2) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "—";
}

export default function SuiteRiskChart({ rows }: Props) {
  const data = rows.map((row) => ({
    name: shortConfigName(row.config),
    fullName: row.config,
    sharpe: row.sharpe ?? 0,
    drawdown: Math.abs(row.max_drawdown_pct ?? 0),
  }));

  return (
    <div className="chart-card">
      <div className="section-label">Risk diagnostics</div>
      <h2 className="section-title">Sharpe vs drawdown profile</h2>
      <div className="chart-card__body">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="sharpeFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#71e7dc" stopOpacity={0.55} />
                <stop offset="95%" stopColor="#71e7dc" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="drawdownFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ffbf75" stopOpacity={0.45} />
                <stop offset="95%" stopColor="#ffbf75" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="rgba(155,168,199,0.12)" vertical={false} />
            <XAxis
              dataKey="name"
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
              formatter={(value, name) => {
                if (String(name) === "drawdown") {
                  return [`${fmtNumber(value)}%`, "Abs drawdown"];
                }
                return [fmtNumber(value, 4), "Sharpe"];
              }}
              labelFormatter={(_, payload) =>
                String(payload?.[0]?.payload?.fullName ?? "")
              }
            />
            <Area
              type="monotone"
              dataKey="sharpe"
              stroke="#71e7dc"
              fill="url(#sharpeFill)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ffbf75"
              fill="url(#drawdownFill)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}