export type TargetName = "staging" | "vault" | "marts";
export type ArtifactName = "manifest.json" | "catalog.json" | "run_results.json" | "graph.js";

export interface RunJobRequest {
  selectors: string[];
  vars: Record<string, string>;
  full_refresh: boolean;
  defer: boolean;
  fail_on_test_failure: boolean;
}

export interface RunJobResponse {
  run_id: string;
  status: string;
  submitted_at?: string;
  target: TargetName;
}

export interface RunStatusResponse {
  run_id: string;
  status: string;
  started_at?: string;
  finished_at?: string;
  duration_sec?: number;
  job_name?: string;
  artifacts: string[];
}

export interface RunLogsResponse {
  run_id: string;
  lines: string[];
  truncated: boolean;
  updated_at?: string;
}

export interface ArtifactEnvelope {
  run_id: string;
  name: ArtifactName;
  etag?: string;
  size?: number;
  content_type?: string;
  cached: boolean;
  content?: Record<string, unknown> | string;
}

export interface RunSummary {
  target: string;
  run_id?: string;
  generated_at?: string;
  dbt_version?: string;
  elapsed_time?: number;
  results_total: number;
  results_passed: number;
  results_failed: number;
  status: string;
}

export interface RunsListResponse {
  total: number;
  items: RunSummary[];
}

export interface ModelItem {
  unique_id: string;
  name: string;
  resource_type: string;
  schema?: string;
  package_name?: string;
  tags?: string[];
  depends_on?: string[];
}

export interface ModelSearchResponse {
  total: number;
  items: ModelItem[];
}

export interface LineageNode {
  id: string;
  name: string;
  resource_type: string;
  schema?: string;
  package_name?: string;
  tags?: string[];
}

export interface LineageEdge {
  source: string;
  target: string;
}

export interface LineageGraphResponse {
  nodes: LineageNode[];
  edges: LineageEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface TestFailure {
  target: string;
  unique_id: string;
  status: string;
  severity: string;
  message?: string;
  execution_time?: number;
}

export interface TestsSummaryResponse {
  summary: Record<string, { total: number; passed: number; failed: number }>;
  failed: TestFailure[];
  failed_total: number;
}
