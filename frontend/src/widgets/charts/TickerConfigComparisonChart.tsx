import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SuiteTickerResult } from "../../shared/types/api";

type Props = {
  rows: SuiteTickerResult[];
  ticker: string;
};

const COLORS = ["#70a5ff", "#71e7dc", "#ffbf75", "#77e0a7"];

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

export default function TickerConfigComparisonChart({ rows, ticker }: Props) {
  const data = rows
    .filter((row) => row.ticker === ticker)
    .map((row) => ({
      name: shortConfigName(row.config),
      fullName: row.config,
      returnValue: row.strat_total_return ?? 0,
      sharpeValue: row.strat_sharpe ?? 0,
    }));

  return (
    <div className="chart-card">
      <div className="section-label">Instrument comparison</div>
      <h2 className="section-title">Configuration sensitivity for {ticker}</h2>
      <div className="chart-card__body">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} barCategoryGap={28}>
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
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
              contentStyle={{
                background: "rgba(10,17,31,0.95)",
                border: "1px solid rgba(114,138,190,0.18)",
                borderRadius: 14,
                color: "#f4f7ff",
              }}
              formatter={(value, name) => {
                if (String(name) === "returnValue") return [`${fmtNumber(value)}%`, "Return"];
                if (String(name) === "sharpeValue") return [fmtNumber(value, 4), "Sharpe"];
                return [fmtNumber(value), String(name)];
              }}
              labelFormatter={(_, payload) => String(payload?.[0]?.payload?.fullName ?? "")}
            />
            <Bar dataKey="returnValue" radius={[10, 10, 0, 0]}>
              {data.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}