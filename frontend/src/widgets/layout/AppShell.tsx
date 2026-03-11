import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview", end: true },
  { to: "/suite-runs", label: "Suite Runs" },
  { to: "/ticker-explorer", label: "Ticker Explorer" },
  { to: "/methodology", label: "Methodology" },
];

export default function AppShell() {
  return (
    <div className="app-shell">
      <div className="background-glow background-glow--blue" />
      <div className="background-glow background-glow--cyan" />
      <div className="background-glow background-glow--amber" />

      <aside className="sidebar">
        <div className="sidebar__inner">
          <div className="brand">
            <div className="brand__eyebrow">Institutional Research Terminal</div>
            <div className="brand__title">ThothMind</div>
            <div className="brand__subtitle">
              Intelligent market analysis and forecasting system for investment decision support
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

          <div className="sidebar-panel">
            <div className="sidebar-panel__label">Execution model</div>
            <div className="sidebar-panel__value">Offline precomputed analytics</div>
            <div className="sidebar-panel__meta">
              Python batch backend • React research frontend
            </div>
          </div>

          <div className="sidebar-panel sidebar-panel--compact">
            <div className="sidebar-panel__label">Current direction</div>
            <div className="sidebar-chip-row">
              <span className="sidebar-chip">M8 true multi</span>
              <span className="sidebar-chip">Curated universe</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}