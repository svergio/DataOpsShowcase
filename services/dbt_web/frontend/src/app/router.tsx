import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { docsRoutes } from "../features/docs/routes";
import { ArtifactsPage } from "../pages/ArtifactsPage";
import { DocsPage } from "../pages/DocsPage";
import { LineagePage } from "../pages/LineagePage";
import { ModelsPage } from "../pages/ModelsPage";
import { RunsPage } from "../pages/RunsPage";
import { TestsPage } from "../pages/TestsPage";

function Shell() {
  return (
    <div style={{ fontFamily: "sans-serif", padding: 16 }}>
      <h1>dbt-web</h1>
      <nav style={{ display: "flex", gap: 12 }}>
        <Link to="/runs">Runs</Link>
        <Link to="/models">Models</Link>
        <Link to="/lineage">Lineage</Link>
        <Link to="/tests">Tests</Link>
        <Link to="/docs">Docs</Link>
        <Link to="/artifacts">Artifacts</Link>
      </nav>
      <hr />
      <Routes>
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/lineage" element={<LineagePage />} />
        <Route path="/tests" element={<TestsPage />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/artifacts" element={<ArtifactsPage />} />
        <Route path={docsRoutes.path} element={docsRoutes.element}>
          {docsRoutes.children?.map((child, idx) => (
            <Route key={idx} path={child.path} element={child.element} />
          ))}
        </Route>
        <Route path="*" element={<Navigate to="/runs" replace />} />
      </Routes>
    </div>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
