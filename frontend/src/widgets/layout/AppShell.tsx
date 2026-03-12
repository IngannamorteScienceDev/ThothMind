import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import type { SuiteRun, SuiteTickerResult } from "../../shared/types/api";
import { loadSuiteRuns, loadSuiteTickerResults } from "../../services/dataLoader";
import { adaptSuiteRuns, adaptSuiteTickerResults } from "../../services/adapters";

const navItems = [
  { to: "/", label: "Overview", end: true },
  { to: "/suite-runs", label: "Experiment Registry" },
  { to: "/ticker-explorer", label: "Instrument Analytics" },
  { to: "/insights", label: "Analytical Conclusions" },
  { to: "/methodology", label: "Architecture & Methodology" },
];

export default function AppShell() {
  const [suiteRuns, setSuiteRuns] = useState<SuiteRun[]>([]);
  const [tickerRows, setTickerRows] = useState<SuiteTickerResult[]>([]);

  useEffect(() => {
    async function bootstrap() {
      const [suiteRaw, tickerRaw] = await Promise.all([
        loadSuiteRuns(),
        loadSuiteTickerResults(),
      ]);

      setSuiteRuns(adaptSuiteRuns(suiteRaw));
      setTickerRows(adaptSuiteTickerResults(tickerRaw));
    }

    bootstrap();
  }, []);

  const snapshot = useMemo(() => {
    const configs = new Set(suiteRuns.map((r) => r.config)).size;
    const stages = new Set(suiteRuns.map((r) => r.stage)).size;
    const universe = suiteRuns.reduce(
      (acc, row) => Math.max(acc, row.n_suite_tickers || 0),
      0
    );
    const instrumentCount = new Set(tickerRows.map((r) => r.ticker)).size;

    return { configs, stages, universe, instrumentCount };
  }, [suiteRuns, tickerRows]);

  return (
    <div className="app-shell">
      <div className="background-glow background-glow--blue" />
      <div className="background-glow background-glow--cyan" />
      <div className="background-glow background-glow--amber" />

      <aside className="sidebar">
        <div className="sidebar__inner">
          <div className="brand">
            <div className="brand-mark">
              <span>T</span>
              <span>M</span>
            </div>
            <div className="brand__eyebrow">Intelligent Market Analysis Platform</div>
            <div className="brand__title">ThothMind</div>
            <div className="brand__subtitle">
              Intelligent market analysis and forecasting system for investment
              decision support
            </div>
          </div>

          <nav className="nav">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? "nav-link nav-link--active" : "nav-link"
                }
              >
                <span className="nav-link__label">{item.label}</span>
                <span className="nav-link__arrow">→</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>

      <main className="main-content">
        <div className="global-snapshot-bar">
          <div className="global-snapshot-bar__title">Research snapshot</div>

          <div className="global-snapshot-chip">
            <span className="global-snapshot-chip__label">Configurations</span>
            <span className="global-snapshot-chip__value">{snapshot.configs}</span>
          </div>

          <div className="global-snapshot-chip">
            <span className="global-snapshot-chip__label">Stages</span>
            <span className="global-snapshot-chip__value">{snapshot.stages}</span>
          </div>

          <div className="global-snapshot-chip">
            <span className="global-snapshot-chip__label">Universe</span>
            <span className="global-snapshot-chip__value">{snapshot.universe}</span>
          </div>

          <div className="global-snapshot-chip">
            <span className="global-snapshot-chip__label">Instruments</span>
            <span className="global-snapshot-chip__value">
              {snapshot.instrumentCount}
            </span>
          </div>

          <div className="global-snapshot-bar__mode">
            Offline experiment registry • multi-ticker analytical snapshot
          </div>
        </div>

        <Outlet />
      </main>
    </div>
  );
}