import type { SuiteRun, SuiteTickerResult, TopRun } from "../shared/types/api";

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asBoolean(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

export function adaptSuiteRuns(raw: unknown[]): SuiteRun[] {
  return raw.map((item) => {
    const row = item as Record<string, unknown>;
    return {
      config: asString(row.config),
      ticker: asString(row.ticker),
      stage: asString(row.stage),
      suite_mode: asString(row.suite_mode),
      n_suite_tickers: Number(row.n_suite_tickers ?? 0),
      is_single_ticker_suite: asBoolean(row.is_single_ticker_suite),
      exclude_from_showcase: asBoolean(row.exclude_from_showcase),
      return_metric_pct: asNumber(row.return_metric_pct),
      actual_rel_return_pct: asNumber(row.actual_rel_return_pct),
      sharpe: asNumber(row.sharpe),
      max_drawdown_pct: asNumber(row.max_drawdown_pct),
      p_value_one_sided: asNumber(row.p_value_one_sided),
      defense_ready_score: asNumber(row.defense_ready_score),
      run_dir: asString(row.run_dir),
    };
  });
}

export function adaptSuiteTickerResults(raw: unknown[]): SuiteTickerResult[] {
  return raw.map((item) => {
    const row = item as Record<string, unknown>;
    return {
      config: asString(row.config),
      ticker: asString(row.ticker),
      status: asString(row.status),
      strat_total_return: asNumber(row.strat_total_return),
      strat_sharpe: asNumber(row.strat_sharpe),
      strat_max_drawdown: asNumber(row.strat_max_drawdown),
      actual_rel_return: asNumber(row.actual_rel_return),
      p_value_one_sided: asNumber(row.p_value_one_sided),
    };
  });
}

export function adaptTopRuns(raw: unknown[]): TopRun[] {
  return raw.map((item) => {
    const row = item as Record<string, unknown>;
    return {
      rank: Number(row.rank ?? 0),
      ticker: asString(row.ticker),
      config: asString(row.config),
      stage: asString(row.stage),
      suite_mode: asString(row.suite_mode),
      n_suite_tickers: Number(row.n_suite_tickers ?? 0),
      return_metric_pct: asNumber(row.return_metric_pct),
      actual_rel_return_pct: asNumber(row.actual_rel_return_pct),
      sharpe: asNumber(row.sharpe),
      max_drawdown_pct: asNumber(row.max_drawdown_pct),
      p_value_one_sided: asNumber(row.p_value_one_sided),
      defense_ready_score: asNumber(row.defense_ready_score),
      run_dir: asString(row.run_dir),
    };
  });
}
