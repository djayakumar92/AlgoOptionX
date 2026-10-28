import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import "./App.css";
import { Sidebar } from "./components/Sidebar";
import AiAnalystPage from "./pages/AiAnalystPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import BacktestPage from "./pages/BacktestPage";
import ChartPage from "./pages/ChartPage";
import CommandCenterPage from "./pages/CommandCenterPage";
import HlcPage from "./pages/HlcPage";
import JournalPage from "./pages/JournalPage";
import LearningLabPage from "./pages/LearningLabPage";
import LivePage from "./pages/LivePage";
import MarketStructurePage from "./pages/MarketStructurePage";
import OptionIntelligencePage from "./pages/OptionIntelligencePage";
import ScenarioEnginePage from "./pages/ScenarioEnginePage";
import SettingsPage from "./pages/SettingsPage";

// The guide is the only page that needs a markdown renderer, and bundling it
// with everything else added ~47 KB gzipped to every trading screen. Loaded on
// demand instead: the pages watched during market hours stay light, and the
// guide costs its own weight only when it is opened.
const GuidePage = lazy(() => import("./pages/GuidePage"));

export default function ResearchApp() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-area">
        <div className="main-area-inner">
          <Routes>
            <Route path="/" element={<CommandCenterPage />} />
            <Route path="/live" element={<LivePage />} />
            <Route path="/market-structure" element={<MarketStructurePage />} />
            <Route path="/option-intelligence" element={<OptionIntelligencePage />} />
            <Route path="/ai-analyst" element={<AiAnalystPage />} />
            <Route path="/scenario-engine" element={<ScenarioEnginePage />} />
            <Route path="/hlc" element={<HlcPage />} />
            <Route path="/chart" element={<ChartPage />} />
            <Route path="/journal" element={<JournalPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
            <Route path="/learning-lab" element={<LearningLabPage />} />
            <Route
              path="/guide"
              element={
                <Suspense fallback={<div className="banner banner-info">Loading the guide…</div>}>
                  <GuidePage />
                </Suspense>
              }
            />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
