import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

type Row = {
  config: string;
  return_metric_pct: number | null;
  max_drawdown_pct: number | null;
  sharpe: number | null;
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

export default function ReturnDrawdownScatterChart({ rows }: Props) {
  const data = rows.map((row) => ({
    name: shortConfigName(row.config),
    fullName: row.config,
    x: Math.abs(row.max_drawdown_pct ?? 0),
    y: row.return_metric_pct ?? 0,
    z: Math.max((row.sharpe ?? 0) * 100, 8),
    sharpe: row.sharpe ?? 0,
  }));

  return (
    <div className="chart-card">
      <div className="section-label">Risk map</div>
      <h2 className="section-title">Return vs drawdown space</h2>
      <div className="chart-card__body">
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 12, right: 12, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="rgba(155,168,199,0.12)" />
            <XAxis
              type="number"
              dataKey="x"
              name="Abs drawdown"
              tick={{ fill: "#9ba8c7", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Return"
              tick={{ fill: "#9ba8c7", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <ZAxis type="number" dataKey="z" range={[90, 420]} />
            <Tooltip
              cursor={{ strokeDasharray: "4 4", stroke: "rgba(255,255,255,0.18)" }}
              contentStyle={{
                background: "rgba(10,17,31,0.95)",
                border: "1px solid rgba(114,138,190,0.18)",
                borderRadius: 14,
                color: "#f4f7ff",
              }}
              formatter={(value, name) => {
                if (String(name) === "Return") return [`${fmtNumber(value)}%`, "Return"];
                if (String(name) === "Abs drawdown") {
                  return [`${fmtNumber(value)}%`, "Abs drawdown"];
                }
                return [fmtNumber(value, 4), String(name)];
              }}
              labelFormatter={(_, payload) => String(payload?.[0]?.payload?.fullName ?? "")}
            />
            <Scatter data={data} fill="#70a5ff" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}