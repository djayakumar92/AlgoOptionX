import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import ScreenBoundary from "./ScreenBoundary";
import PublicShell from "./PublicShell";
import HomePage from "../features/marketing/pages/HomePage";
import WalkthroughPage from "../features/marketing/pages/WalkthroughPage";
import {PricingPage,BillingPage} from "../features/billing/BillingPages";
import {IdentityProvider,TenantBoundary,AccountBoundary} from "../features/identity/IdentityContext";
import {IdentityPage, AccountPage} from "../features/identity/IdentityPages";
import StartPage from "../features/onboarding/pages/StartPage";

const InsightsPage = lazy(() => import("../features/insights/InsightsPage"));
const OperationsPage = lazy(() => import("../features/operations/OperationsPage"));
const ResearchJobs = lazy(() => import("../features/research-jobs/ResearchJobs"));
const BrokerPage = lazy(() => import("../features/brokers/BrokerPage"));
const MfaPage = lazy(() => import("../features/identity/MfaPage"));
const TradePage = lazy(() => import("../features/charts/TradePage"));
const WorkspacePage = lazy(() => import("../features/charts/WorkspacePage"));
const StrategyStudio = lazy(() => import("../features/studio/StrategyStudio"));
const Workspace = lazy(() => import("./WorkspaceApp"));
const DemoWorkspace = lazy(() => import("../features/demo/DemoWorkspace"));

function LegacyRoute() {
  const location = useLocation();
  return (
    <Navigate
      replace
      to={`/app${location.pathname}${location.search}${location.hash}`}
    />
  );
}

export default function ProductRouter() {
  return (
    <IdentityProvider><ScreenBoundary><Routes>
      <Route element={<PublicShell />}>
        <Route index element={<HomePage />} />
        <Route path="walkthrough" element={<WalkthroughPage />} />
        <Route path="trade" element={<Suspense fallback={<p role="status">Loading paper execution…</p>}><TenantBoundary><TradePage /></TenantBoundary></Suspense>} />
        <Route path="workspaces" element={<Suspense fallback={<p role="status">Loading chart workspaces…</p>}><TenantBoundary><WorkspacePage /></TenantBoundary></Suspense>} />
        <Route path="studio" element={<Suspense fallback={<p role="status">Loading Strategy Studio…</p>}><TenantBoundary><StrategyStudio /></TenantBoundary></Suspense>} />
        <Route path="insights" element={<Suspense fallback={<p role="status">Loading grounded reports…</p>}><TenantBoundary><InsightsPage /></TenantBoundary></Suspense>} />
        <Route path="operations" element={<Suspense fallback={<p role="status">Loading workspace operations…</p>}><TenantBoundary><OperationsPage /></TenantBoundary></Suspense>} />
        <Route path="research-jobs" element={<Suspense fallback={<p role="status">Loading research jobs…</p>}><TenantBoundary><ResearchJobs /></TenantBoundary></Suspense>} />
        <Route path="brokers" element={<Suspense fallback={<p role="status">Loading broker connections…</p>}><TenantBoundary><BrokerPage /></TenantBoundary></Suspense>} />
        <Route path="pricing" element={<PricingPage />} />
        <Route path="billing" element={<TenantBoundary><BillingPage /></TenantBoundary>} />
        <Route path="login" element={<IdentityPage key="login" mode="login" />} />
        <Route path="signup" element={<IdentityPage key="signup" mode="signup" />} />
        <Route path="recover" element={<IdentityPage key="recover" mode="recover" />} />
        <Route path="reset-password" element={<IdentityPage key="reset" mode="reset" />} />
        <Route path="accept-invite" element={<IdentityPage key="invite" mode="invite" />} />
        <Route path="verify-email" element={<IdentityPage key="verify" mode="verify" />} />
        <Route path="account/mfa" element={<Suspense fallback={<p role="status">Loading security settings…</p>}><AccountBoundary><MfaPage /></AccountBoundary></Suspense>} />
        <Route path="account" element={<AccountBoundary><AccountPage /></AccountBoundary>} />
        <Route path="app/start" element={<StartPage />} />
      </Route>
      <Route
        path="demo/*"
        element={
          <Suspense fallback={<p role="status">Loading synthetic demo…</p>}>
            <TenantBoundary><DemoWorkspace /></TenantBoundary>
          </Suspense>
        }
      />
      <Route
        path="app/*"
        element={
          <Suspense fallback={<p role="status">Loading original workspace…</p>}>
            <TenantBoundary><Workspace /></TenantBoundary>
          </Suspense>
        }
      />
      <Route path="*" element={<LegacyRoute />} />
    </Routes></ScreenBoundary></IdentityProvider>
  );
}
