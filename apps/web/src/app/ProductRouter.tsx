import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import PublicShell from "./PublicShell";
import HomePage from "../features/marketing/pages/HomePage";
import WalkthroughPage from "../features/marketing/pages/WalkthroughPage";
import StartPage from "../features/onboarding/pages/StartPage";
const Workspace = lazy(() => import("./WorkspaceApp"));
function LegacyRoute() { const location = useLocation(); return <Navigate replace to={`/app${location.pathname}${location.search}${location.hash}`} />; }
export default function ProductRouter() {
  return <Routes><Route element={<PublicShell />}><Route index element={<HomePage />} /><Route path="walkthrough" element={<WalkthroughPage />} /><Route path="app/start" element={<StartPage />} /></Route><Route path="app/*" element={<Suspense fallback={<p role="status">Loading workspace…</p>}><Workspace /></Suspense>} /><Route path="*" element={<LegacyRoute />} /></Routes>;
}
