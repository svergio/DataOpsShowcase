import { Outlet, useParams } from "react-router-dom";

function DocsLayout() {
  return (
    <div>
      <h2>dbt Docs</h2>
      <Outlet />
    </div>
  );
}

function ModelDocPage() {
  const { modelUniqueId } = useParams();
  return <div>Model doc: {modelUniqueId}</div>;
}

function SourceDocPage() {
  const { sourceUniqueId } = useParams();
  return <div>Source doc: {sourceUniqueId}</div>;
}

function TestDocPage() {
  const { testUniqueId } = useParams();
  return <div>Test doc: {testUniqueId}</div>;
}

export const docsRoutes = {
  path: "/docs",
  element: <DocsLayout />,
  children: [
    { path: "models/:modelUniqueId", element: <ModelDocPage /> },
    { path: "sources/:sourceUniqueId", element: <SourceDocPage /> },
    { path: "tests/:testUniqueId", element: <TestDocPage /> }
  ]
};
