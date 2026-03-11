import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SuiteTickerResult } from "../../shared/types/api";

type Props = {
  rows: SuiteTickerResult[];
};

function buildHistogram(values: number[]) {
  const bins = [
    { min: -1000, max: 0, label: "< 0" },
    { min: 0, max: 25, label: "0–25" },
    { min: 25, max: 50, label: "25–50" },
    { min: 50, max: 75, label: "50–75" },
    { min: 75, max: 100, label: "75–100" },
    { min: 100, max: 150, label: "100–150" },
    { min: 150, max: 9999, label: "150+" },
  ];

  return bins.map((bin) => ({
    label: bin.label,
    count: values.filter((v) => v >= bin.min && v < bin.max).length,
  }));
}

export default function TickerReturnDistributionChart({ rows }: Props) {
  const values = rows
    .map((row) => row.strat_total_return)
    .filter((v): v is number => typeof v === "number");

  const data = buildHistogram(values);

  return (
    <div className="chart-card">
      <div className="section-label">Distribution</div>
      <h2 className="section-title">Per-ticker return distribution</h2>
      <div className="chart-card__body">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} barCategoryGap={18}>
            <CartesianGrid stroke="rgba(155,168,199,0.12)" vertical={false} />
            <XAxis
              dataKey="label"
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
              formatter={(value: number) => [value, "Tickers"]}
            />
            <Bar dataKey="count" fill="#71e7dc" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}