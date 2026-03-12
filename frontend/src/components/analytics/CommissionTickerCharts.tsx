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
  tickerRows: SuiteTickerResult[];
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

export default function CommissionTickerCharts({ tickerRows }: Props) {
  const grouped = new Map<
    string,
    { ticker: string; bestGap: number; avgSharpe: number; avgReturn: number; worstDd: number; count: number }
  >();

  for (const row of tickerRows) {
    const current = grouped.get(row.ticker) ?? {
      ticker: row.ticker,
      bestGap: Number.NEGATIVE_INFINITY,
      avgSharpe: 0,
      avgReturn: 0,
      worstDd: 0,
      count: 0,
    };

    current.bestGap = Math.max(current.bestGap, row.actual_rel_return ?? Number.NEGATIVE_INFINITY);
    current.avgSharpe += row.strat_sharpe ?? 0;
    current.avgReturn += row.strat_total_return ?? 0;
    current.worstDd = Math.min(current.worstDd, row.strat_max_drawdown ?? 0);
    current.count += 1;

    grouped.set(row.ticker, current);
  }

  const aggregated = Array.from(grouped.values()).map((row) => ({
    ticker: row.ticker,
    bestGap: Number.isFinite(row.bestGap) ? row.bestGap : 0,
    avgSharpe: row.count ? row.avgSharpe / row.count : 0,
    avgReturn: row.count ? row.avgReturn / row.count : 0,
    worstDd: row.worstDd,
  }));

  const topTickers = [...aggregated].sort((a, b) => b.bestGap - a.bestGap).slice(0, 10);
  const bottomTickers = [...aggregated].sort((a, b) => a.bestGap - b.bestGap).slice(0, 10);

  const configAgg = new Map<string, { config: string; avgReturn: number; avgSharpe: number; n: number }>();
  for (const row of tickerRows) {
    const key = shortConfigName(row.config);
    const current = configAgg.get(key) ?? { config: key, avgReturn: 0, avgSharpe: 0, n: 0 };
    current.avgReturn += row.strat_total_return ?? 0;
    current.avgSharpe += row.strat_sharpe ?? 0;
    current.n += 1;
    configAgg.set(key, current);
  }

  const configRows = Array.from(configAgg.values()).map((row) => ({
    config: row.config,
    avgReturn: row.n ? row.avgReturn / row.n : 0,
    avgSharpe: row.n ? row.avgSharpe / row.n : 0,
  }));

  return (
    <div className="page" style={{ gap: 18 }}>
      <section className="terminal-card terminal-card--featured">
        <div className="section-label">Extended instrument analytics</div>
        <h2 className="section-title">Cross-instrument comparison layer</h2>
        <p className="section-text">
          These charts expand ticker-level diagnostics beyond a single selected
          instrument. They reveal which instruments show the strongest benchmark gap,
          where the weakest relative behavior is concentrated, and how average
          configuration performance behaves across the currently filtered universe.
        </p>
      </section>

      <div className="chart-grid chart-grid--triple">
        <div className="chart-card">
          <div className="section-label">Leaders</div>
          <h2 className="section-title">Top benchmark outperformers</h2>
          <div className="chart-card__body">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={topTickers} layout="vertical" margin={{ top: 6, right: 12, left: 8, bottom: 6 }}>
                <CartesianGrid stroke="rgba(155,168,199,0.12)" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: "#9ba8c7", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="ticker"
                  width={56}
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
                />
                <Bar dataKey="bestGap" radius={[0, 10, 10, 0]} fill="#77e0a7" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="section-label">Laggards</div>
          <h2 className="section-title">Weakest benchmark gaps</h2>
          <div className="chart-card__body">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={bottomTickers} layout="vertical" margin={{ top: 6, right: 12, left: 8, bottom: 6 }}>
                <CartesianGrid stroke="rgba(155,168,199,0.12)" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: "#9ba8c7", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="ticker"
                  width={56}
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
                />
                <Bar dataKey="bestGap" radius={[0, 10, 10, 0]} fill="#ff9a9a" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="section-label">Configuration profile</div>
          <h2 className="section-title">Average return by configuration</h2>
          <div className="chart-card__body">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={configRows} margin={{ top: 12, right: 12, left: 0, bottom: 18 }}>
                <CartesianGrid stroke="rgba(155,168,199,0.12)" vertical={false} />
                <XAxis
                  dataKey="config"
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
                  formatter={(value) => [`${fmt(value)}%`, "Average return"]}
                />
                <Bar dataKey="avgReturn" radius={[10, 10, 0, 0]} fill="#70a5ff" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}