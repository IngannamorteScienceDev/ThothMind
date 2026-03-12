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

type TickerRow = {
  ticker: string;
  config: string;
  strat_total_return?: number;
  strat_sharpe?: number;
  strat_max_drawdown?: number;
  actual_rel_return?: number;
  p_value_one_sided?: number;
};

type Props = {
  tickerRows: TickerRow[];
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

export function CommissionTickerCharts({ tickerRows }: Props) {
  const grouped = new Map<
    string,
    { ticker: string; bestGap: number; avgSharpe: number; worstDd: number; count: number }
  >();

  for (const row of tickerRows) {
    const current = grouped.get(row.ticker) ?? {
      ticker: row.ticker,
      bestGap: Number.NEGATIVE_INFINITY,
      avgSharpe: 0,
      worstDd: 0,
      count: 0,
    };

    current.bestGap = Math.max(current.bestGap, row.actual_rel_return ?? -9999);
    current.avgSharpe += row.strat_sharpe ?? 0;
    current.worstDd = Math.min(current.worstDd, row.strat_max_drawdown ?? 0);
    current.count += 1;

    grouped.set(row.ticker, current);
  }

  const aggregated = Array.from(grouped.values()).map((row) => ({
    ticker: row.ticker,
    bestGap: row.bestGap,
    avgSharpe: row.count ? row.avgSharpe / row.count : 0,
    worstDd: row.worstDd,
  }));

  const topTickers = [...aggregated]
    .sort((a, b) => b.bestGap - a.bestGap)
    .slice(0, 12);

  const bottomTickers = [...aggregated]
    .sort((a, b) => a.bestGap - b.bestGap)
    .slice(0, 12);

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
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <section className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6 backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-cyan-300/90">
          leaders
        </div>
        <h3 className="mb-4 text-2xl font-semibold text-white">Top benchmark outperformers</h3>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topTickers} layout="vertical" margin={{ top: 6, right: 12, left: 8, bottom: 6 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.10)" horizontal={false} />
              <XAxis
                type="number"
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
              />
              <YAxis
                type="category"
                dataKey="ticker"
                width={56}
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(2,6,23,0.95)",
                }}
                formatter={(v: number) => [fmt(v), "Excess return %"]}
              />
              <Bar dataKey="bestGap" radius={[0, 12, 12, 0]} fill="#34d399" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6 backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-cyan-300/90">
          laggards
        </div>
        <h3 className="mb-4 text-2xl font-semibold text-white">Weakest benchmark gaps</h3>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bottomTickers} layout="vertical" margin={{ top: 6, right: 12, left: 8, bottom: 6 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.10)" horizontal={false} />
              <XAxis
                type="number"
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
              />
              <YAxis
                type="category"
                dataKey="ticker"
                width={56}
                stroke="rgba(226,232,240,0.7)"
                tick={{ fill: "rgba(226,232,240,0.8)", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 16,
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(2,6,23,0.95)",
                }}
                formatter={(v: number) => [fmt(v), "Excess return %"]}
              />
              <Bar dataKey="bestGap" radius={[0, 12, 12, 0]} fill="#fb7185" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6 backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.28em] text-cyan-300/90">
          configuration profile
        </div>
        <h3 className="mb-4 text-2xl font-semibold text-white">Average return by configuration</h3>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={configRows} margin={{ top: 12, right: 12, left: 0, bottom: 18 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.10)" vertical={false} />
              <XAxis
                dataKey="config"
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
                formatter={(v: number, n: string) => [
                  fmt(v),
                  n === "avgReturn" ? "Average return %" : "Average Sharpe",
                ]}
              />
              <Bar dataKey="avgReturn" radius={[12, 12, 0, 0]}>
                {configRows.map((_, idx) => (
                  <Cell
                    key={idx}
                    fill={["#7dd3fc", "#67e8f9", "#a78bfa", "#fbbf24", "#34d399", "#fb7185"][idx % 6]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}