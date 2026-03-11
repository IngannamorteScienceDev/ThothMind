import { createBrowserRouter } from "react-router-dom";
import AppShell from "../widgets/layout/AppShell";
import OverviewPage from "../pages/OverviewPage";
import SuiteRunsPage from "../pages/SuiteRunsPage";
import SuiteDetailPage from "../pages/SuiteDetailPage";
import TickerExplorerPage from "../pages/TickerExplorerPage";
import MethodologyPage from "../pages/MethodologyPage";
import InsightsPage from "../pages/InsightsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: "suite-runs", element: <SuiteRunsPage /> },
      { path: "suite-runs/:configId", element: <SuiteDetailPage /> },
      { path: "ticker-explorer", element: <TickerExplorerPage /> },
      { path: "insights", element: <InsightsPage /> },
      { path: "methodology", element: <MethodologyPage /> },
    ],
  },
]);