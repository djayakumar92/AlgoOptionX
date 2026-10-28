import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/base.css";
import Workspace from "./app/WorkspaceApp.tsx";
const App =
  import.meta.env.VITE_WORKSPACE === "research"
    ? lazy(() => import("./features/research/ResearchApp.tsx"))
    : Workspace;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Suspense fallback={<p>Loading AlgoOptionX…</p>}>
        <App />
      </Suspense>
    </BrowserRouter>
  </StrictMode>,
);
