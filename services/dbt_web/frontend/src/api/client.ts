import type {
  ArtifactEnvelope,
  ArtifactName,
  LineageGraphResponse,
  ModelSearchResponse,
  RunJobRequest,
  RunJobResponse,
  RunLogsResponse,
  RunStatusResponse,
  RunsListResponse,
  TargetName,
  TestsSummaryResponse
} from "./contracts";

const jsonHeaders = { "Content-Type": "application/json" };

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.append(k, String(v));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  runJob(target: TargetName, payload: RunJobRequest) {
    return request<RunJobResponse>(`/api/v1/runs/${target}`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    });
  },
  getRun(runId: string) {
    return request<RunStatusResponse>(`/api/v1/runs/${runId}`);
  },
  getRunLogs(runId: string) {
    return request<RunLogsResponse>(`/api/v1/runs/${runId}/logs`);
  },
  getArtifact(runId: string, name: ArtifactName) {
    return request<ArtifactEnvelope>(`/api/v1/runs/${runId}/artifacts/${name}`);
  },
  listRuns(filters: { status?: string; target?: string; limit?: number } = {}) {
    return request<RunsListResponse>(`/api/v1/runs${buildQuery(filters)}`);
  },
  searchModels(filters: {
    query?: string;
    tags?: string;
    resource_type?: string;
    schema?: string;
    package_name?: string;
  } = {}) {
    return request<ModelSearchResponse>(`/api/v1/models${buildQuery(filters)}`);
  },
  getLineageGraph(filters: {
    resource_type?: string;
    schema?: string;
    package_name?: string;
    tag?: string;
  } = {}) {
    return request<LineageGraphResponse>(`/api/v1/lineage${buildQuery(filters)}`);
  },
  getTestsSummary(filters: { target?: string; severity?: string } = {}) {
    return request<TestsSummaryResponse>(`/api/v1/tests/summary${buildQuery(filters)}`);
  },
  getDocsManifest() {
    return request<Record<string, unknown>>(`/api/v1/docs/manifest`);
  },
  getDocsCatalog() {
    return request<Record<string, unknown>>(`/api/v1/docs/catalog`);
  }
};
