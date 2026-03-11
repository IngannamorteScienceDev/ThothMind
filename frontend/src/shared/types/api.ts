export type NullableNumber = number | null;

export type SuiteRun = {
  config: string;
  ticker: string;
  stage: string;
  suite_mode: string;
  n_suite_tickers: number;
  is_single_ticker_suite: boolean;
  exclude_from_showcase: boolean;
  return_metric_pct: NullableNumber;
  actual_rel_return_pct: NullableNumber;
  sharpe: NullableNumber;
  max_drawdown_pct: NullableNumber;
  p_value_one_sided: NullableNumber;
  defense_ready_score: NullableNumber;
  run_dir: string;
};

export type SuiteTickerResult = {
  config: string;
  ticker: string;
  status?: string;
  strat_total_return?: NullableNumber;
  strat_sharpe?: NullableNumber;
  strat_max_drawdown?: NullableNumber;
  actual_rel_return?: NullableNumber;
  p_value_one_sided?: NullableNumber;
};

export type TopRun = {
  rank?: number;
  ticker: string;
  config: string;
  stage?: string;
  suite_mode?: string;
  n_suite_tickers?: number;
  return_metric_pct?: NullableNumber;
  actual_rel_return_pct?: NullableNumber;
  sharpe?: NullableNumber;
  max_drawdown_pct?: NullableNumber;
  p_value_one_sided?: NullableNumber;
  defense_ready_score?: NullableNumber;
  run_dir?: string;
};

export type CuratedManifest = {
  selected_csv?: string;
  output_root?: string;
  stocks_count?: number;
  etfs_count?: number;
  total_expected?: number;
  total_copied?: number;
  missing_files_count?: number;
  missing_files?: string[];
};

export type ArtifactFreshness = {
  suiteIndexLastModified: string | null;
  tickerIndexLastModified: string | null;
  topReturnLastModified: string | null;
  topDefenseLastModified: string | null;
};