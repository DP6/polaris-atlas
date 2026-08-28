import { httpClient } from '@/lib/http-client'
import type {
  AccessRequest,
  AccessRequestAnalyticsResponse,
  AccessRequestStatus,
  AccessRequestsListResponse,
  EventCacheRunsResponse,
  EventCacheStatusResponse,
  FavoritesAnalyticsResponse,
  HubGroup,
  HubGroupsListResponse,
  HubProject,
  HubProjectsListResponse,
  HubUser,
  HubUsersListResponse,
  LoginAnalyticsResponse,
  NavigationAnalyticsResponse,
  PiiScanActivityResponse,
  ProfilingActivityResponse,
  ProjectChecklistResponse,
  ProjectUsersResponse,
  RetentionFunnelResponse,
  UpsertHubGroupRequest,
  UpsertHubProjectRequest,
  UpsertHubUserRequest,
  UsageHeatmapResponse,
  WorkspaceGroupsListResponse,
} from '@/types/admin'

export const adminApi = {
  // Dispara sob demanda o Cloud Run Job de refresh do cache de audit log
  // (lineage/acesso/órfãs/FinOps/Storage). 202 sem corpo relevante: só
  // confirma o disparo, não espera o Job terminar. forceFull=true (toggle
  // "forçar completo") faz o Job re-escanear a janela inteira em vez do
  // delta incremental.
  refreshEventCache: (forceFull = false) =>
    httpClient.post<void>(
      `/api/v1/admin/event-cache/refresh${forceFull ? '?force_full=true' : ''}`,
    ),

  // Freshness do cache de audit log por projeto × domínio — tudo do
  // Firestore, barato de fazer polling frequente.
  getEventCacheStatus: () =>
    httpClient.get<EventCacheStatusResponse>('/api/v1/admin/event-cache/status'),

  // Histórico completo de execuções do Job de refresh (~200 retidas) — a
  // tela filtra e pagina no cliente.
  getEventCacheRuns: () => httpClient.get<EventCacheRunsResponse>('/api/v1/admin/event-cache/runs'),

  listUsers: () => httpClient.get<HubUsersListResponse>('/api/v1/admin/users'),

  upsertUser: (email: string, request: UpsertHubUserRequest) =>
    httpClient.put<HubUser>(`/api/v1/admin/users/${encodeURIComponent(email)}`, request),

  removeUser: (email: string) =>
    httpClient.delete<undefined>(`/api/v1/admin/users/${encodeURIComponent(email)}`),

  listProjects: () => httpClient.get<HubProjectsListResponse>('/api/v1/admin/projects'),

  upsertProject: (projectId: string, request: UpsertHubProjectRequest) =>
    httpClient.put<HubProject>(`/api/v1/admin/projects/${encodeURIComponent(projectId)}`, request),

  removeProject: (projectId: string) =>
    httpClient.delete<undefined>(`/api/v1/admin/projects/${encodeURIComponent(projectId)}`),

  // Checklist best-effort do onboarding (BigQuery/Logging/Storage) —
  // probing real de cada API, sem exigir nenhuma role nova da SA do Hub.
  // Ver docs/specs/admin.md, "Checklist de onboarding".
  getProjectChecklist: (projectId: string) =>
    httpClient.get<ProjectChecklistResponse>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/checklist`,
    ),

  getProjectUsers: (projectId: string) =>
    httpClient.get<ProjectUsersResponse>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/users`,
    ),

  grantProjectAccess: (projectId: string, email: string) =>
    httpClient.post<HubUser>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/users/${encodeURIComponent(email)}`,
    ),

  revokeProjectAccess: (projectId: string, email: string) =>
    httpClient.delete<undefined>(
      `/api/v1/admin/projects/${encodeURIComponent(projectId)}/users/${encodeURIComponent(email)}`,
    ),

  listGroups: () => httpClient.get<HubGroupsListResponse>('/api/v1/admin/groups'),

  upsertGroup: (groupId: string, request: UpsertHubGroupRequest) =>
    httpClient.put<HubGroup>(`/api/v1/admin/groups/${encodeURIComponent(groupId)}`, request),

  removeGroup: (groupId: string) =>
    httpClient.delete<undefined>(`/api/v1/admin/groups/${encodeURIComponent(groupId)}`),

  listWorkspaceGroups: () =>
    httpClient.get<WorkspaceGroupsListResponse>('/api/v1/admin/workspace-groups'),

  listAccessRequests: (status?: AccessRequestStatus) =>
    httpClient.get<AccessRequestsListResponse>(
      `/api/v1/admin/access-requests${status ? `?status=${status}` : ''}`,
    ),

  approveAccessRequest: (requestId: string) =>
    httpClient.post<AccessRequest>(
      `/api/v1/admin/access-requests/${encodeURIComponent(requestId)}/approve`,
    ),

  denyAccessRequest: (requestId: string) =>
    httpClient.post<AccessRequest>(
      `/api/v1/admin/access-requests/${encodeURIComponent(requestId)}/deny`,
    ),

  getLoginAnalytics: (lookbackDays?: number) =>
    httpClient.get<LoginAnalyticsResponse>(
      `/api/v1/admin/analytics/logins${lookbackDays ? `?lookback_days=${lookbackDays}` : ''}`,
    ),

  getFavoritesAnalytics: () =>
    httpClient.get<FavoritesAnalyticsResponse>('/api/v1/admin/analytics/favorites'),

  getProfilingActivity: (limit?: number) =>
    httpClient.get<ProfilingActivityResponse>(
      `/api/v1/admin/analytics/profiling${limit ? `?limit=${limit}` : ''}`,
    ),

  getAccessRequestAnalytics: () =>
    httpClient.get<AccessRequestAnalyticsResponse>('/api/v1/admin/analytics/access-requests'),

  getNavigationAnalytics: () =>
    httpClient.get<NavigationAnalyticsResponse>('/api/v1/admin/analytics/navigation'),

  getPiiScanActivity: (limit?: number) =>
    httpClient.get<PiiScanActivityResponse>(
      `/api/v1/admin/analytics/pii-scans${limit ? `?limit=${limit}` : ''}`,
    ),

  getUsageHeatmap: (lookbackDays?: number) =>
    httpClient.get<UsageHeatmapResponse>(
      `/api/v1/admin/analytics/usage-heatmap${lookbackDays ? `?lookback_days=${lookbackDays}` : ''}`,
    ),

  getRetentionFunnel: (lookbackDays?: number) =>
    httpClient.get<RetentionFunnelResponse>(
      `/api/v1/admin/analytics/retention-funnel${lookbackDays ? `?lookback_days=${lookbackDays}` : ''}`,
    ),
}
