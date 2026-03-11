import { createBrowserRouter } from "react-router-dom";
import AppShell from "../widgets/layout/AppShell";
import OverviewPage from "../pages/OverviewPage";
import SuiteRunsPage from "../pages/SuiteRunsPage";
import TickerExplorerPage from "../pages/TickerExplorerPage";
import MethodologyPage from "../pages/MethodologyPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: "suite-runs", element: <SuiteRunsPage /> },
      { path: "ticker-explorer", element: <TickerExplorerPage /> },
      { path: "methodology", element: <MethodologyPage /> },
    ],
  },
]);
