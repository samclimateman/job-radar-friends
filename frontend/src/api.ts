// Vite proxies /api in dev; FastAPI serves the built frontend in production.
const BASE = '/api'

export interface Job {
  id: string
  title: string
  organization: string
  location: string | null
  remote_status: string | null
  source: string
  source_url: string
  application_status: string
  lifecycle_status: string
  is_excluded: boolean
  exclusion_reason: string | null
  first_seen_at: string | null
  deadline: string | null
  strategic_fit_score: number
  geo_score: number
  narrative_score: number
  policy_score: number
  role_type: string | null
  org_type: string | null
  notes: string | null
}

export interface Stats {
  jobs: number
  sources: number
  issues: number
  last_refresh: string | null
}

export interface RadarJob {
  id: string
  title: string
  organization: string
  location: string | null
  source_url: string
  strategic_fit_score: number
  first_seen_at: string | null
  last_seen_at: string | null
}

export interface Radar {
  new: RadarJob[]
  reappeared: RadarJob[]
  changed: RadarJob[]
}

export interface JobDetail extends Job {
  raw_description: string
  source_job_id: string | null
  last_seen_at: string | null
  last_changed_at: string | null
  times_seen: number
  missed_scans: number
  classification_data: Record<string, unknown>
  created_at: string
  updated_at: string
  explanation_json: string | null
}

export interface SourceResult {
  source_id: string
  org_name: string
  url: string
  platform: string
  status: string
  notes: string | null
  success: boolean
  manual_review_needed: boolean
  likely_broken_url: boolean
  jobs_found: number
  jobs_new: number
  jobs_updated: number
  jobs_excluded: number
  skipped: boolean
  error: string | null
  fetch_ms: number
  total_ms: number
  confidence_label: string | null
  confidence_score: number | null
  confidence_note: string | null
}

export interface SourceUpdate {
  organization: string | null
  url: string
  notes: string | null
}

export interface SourceHealthSummary {
  generated_at: string
  previous_successful_refresh_at: string | null
  summary: {
    sources_attempted: number
    sources_succeeded: number
    sources_failed: number
    total_new: number
    total_updated: number
    total_excluded: number
    total_stale: number
  }
  results: SourceResult[]
}

export interface RefreshStatus {
  running: boolean
  done: boolean
  error: string | null
  new_jobs: number
  failed: number
}

export interface RefreshProgress {
  running: boolean
  done: boolean
  jobs_found: number
  sources: {
    source_id: string
    organization: string
    status: string
    jobs_found: number
    new_jobs_found: number
    error: string | null
  }[]
}

export interface Application {
  id: string
  job_id: string
  title: string
  organization: string
  location: string | null
  source_url: string
  strategic_fit_score: number
  application_status: string
  interview_stage: string | null
  outcome: string | null
  outcome_notes: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
}

export interface Note {
  id: string
  title: string
  body_markdown: string
  note_type: string
  linked_entity_type: string | null
  linked_entity_id: string | null
  tags: string[]
  pinned: boolean
  archived: boolean
  created_at: string
  updated_at: string
  deleted_at: string | null
}

export interface OnboardingSource {
  organization: string
  url: string
  notes: string
  priority: number | null
  verified: boolean
  llm_suggested: boolean
  review_status: string
}

export interface OnboardingAnswers {
  name: string
  current_role: string
  ideal_role: string
  locations: string[]
  location_policy: 'flexible' | 'prefer' | 'strict'
  remote_policy: 'any_remote' | 'target_region_remote' | 'no_remote_only'
  unknown_location_policy: 'keep' | 'review' | 'exclude'
  avoid_constraints: string
  target_titles: string
  themes: string[]
  custom_themes: string
  blocked_terms: string
  role_types_to_avoid: string[]
  sources: OnboardingSource[]
  strategy_summary: string
}

export interface OnboardingState {
  completed: boolean
  partial: boolean
  last_step: number
  answers: OnboardingAnswers
}

export interface OnboardingCompleteResult {
  ok: boolean
  sources_added: number
  partial: boolean
  sources: {
    id: string
    organization: string | null
    url: string
    platform: string
    status: string
    note: string | null
  }[]
}

export interface DataLocation {
  data_dir: string
  database_path: string
  database_exists: boolean
}

export interface CommunityPack {
  schema_version: number
  domain: string
  organization: string
  careers_url: string
  platform: string
  tags?: string[]
  region?: string
  last_verified?: string
  confidence?: string
  notes?: string
  already_added?: boolean
}

export interface CommunityStatus {
  available: boolean
  pack_count: number
  fetched_at: string | null
  registry_url: string
}

export interface CommunitySharePayload {
  schema_version: number
  domain: string
  organization: string
  careers_url: string
  platform: string
  last_verified: string
  confidence?: string
}

export interface CommunityShare {
  payload: CommunitySharePayload
  issue_url: string
  domain_missing: boolean
}

export interface CreatedSource {
  id: string
  organization: string | null
  url: string
  platform: string
  status: string
}

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  stats: () => get<Stats>('/stats'),
  radar: () => get<Radar>('/radar'),
  jobs: (view = 'best', limit = 200, offset = 0) =>
    get<Job[]>('/jobs', { view, limit, offset }),
  job: (id: string) => get<JobDetail>(`/jobs/${id}`),
  updateStatus: (id: string, status: string) =>
    patch<{ ok: boolean }>(`/jobs/${id}/status`, { status }),
  updateJobNote: (id: string, notes: string) =>
    patch<{ ok: boolean }>(`/jobs/${id}/note`, { notes }),
  sourceHealth: () => get<SourceHealthSummary | null>('/sources/health'),
  updateSource: (id: string, body: SourceUpdate) =>
    patch<{ ok: boolean }>(`/sources/${id}`, body),
  markSourceChecked: (id: string) => post<{ ok: boolean }>(`/sources/${id}/checked`),
  disableSource: (id: string) => post<{ ok: boolean }>(`/sources/${id}/disable`),
  enableSource: (id: string) => post<{ ok: boolean }>(`/sources/${id}/enable`),
  retrySource: (id: string) =>
    post<{ ok: boolean; sources_succeeded: number; sources_failed: number; jobs_found: number; new_jobs_found: number }>(`/sources/${id}/retry`),
  deleteSource: (id: string) => del<{ ok: boolean }>(`/sources/${id}`),
  startRefresh: () => post<RefreshStatus>('/refresh/start'),
  refreshStatus: () => get<RefreshStatus>('/refresh/status'),
  refreshProgress: () => get<RefreshProgress>('/refresh/progress'),
  getBlocklist: () => get<string[]>('/blocklist'),
  addToBlocklist: (phrase: string) => post<string[]>('/blocklist', { phrase }),
  removeFromBlocklist: (phrase: string) => del<string[]>(`/blocklist/${encodeURIComponent(phrase)}`),
  applications: () => get<Application[]>('/applications'),
  updateAppStage: (id: string, stage: string | null) =>
    patch<{ ok: boolean }>(`/applications/${id}/stage`, { stage }),
  updateAppOutcome: (id: string, outcome: string, notes?: string) =>
    patch<{ ok: boolean }>(`/applications/${id}/outcome`, { outcome, notes: notes ?? null }),
  notes: (note_type?: string) =>
    get<Note[]>('/notes', note_type ? { note_type } : undefined),
  trashNotes: () => get<Note[]>('/notes/trash'),
  pinnedNotes: () => get<Note[]>('/notes/pinned'),
  createNote: (body: string, title?: string, note_type?: string) =>
    post<Note>('/notes', { body, title: title ?? null, note_type: note_type ?? 'general' }),
  updateNote: (id: string, patch_data: Partial<Pick<Note, 'title' | 'body_markdown' | 'note_type' | 'pinned'>>) =>
    patch<Note>(`/notes/${id}`, patch_data),
  archiveNote: (id: string) => post<{ ok: boolean }>(`/notes/${id}/archive`),
  deleteNote: (id: string) => del<{ ok: boolean }>(`/notes/${id}`),
  restoreNote: (id: string) => post<{ ok: boolean }>(`/notes/${id}/restore`),
  purgeNote: (id: string) => del<{ ok: boolean }>(`/notes/${id}/purge`),
  emptyTrash: () => del<{ ok: boolean }>('/notes/trash'),
  onboarding: () => get<OnboardingState>('/onboarding'),
  saveOnboarding: (state: Partial<Pick<OnboardingState, 'partial' | 'last_step' | 'answers'>>) =>
    patch<OnboardingState>('/onboarding', state),
  completeOnboarding: (answers: OnboardingAnswers) =>
    post<OnboardingCompleteResult>('/onboarding/complete', answers),
  dataLocation: () => get<DataLocation>('/data/location'),
  addSource: (organization: string | null, url: string) =>
    post<{ ok: boolean; source: CreatedSource }>('/sources', { organization, url }),
  communityStatus: () => get<CommunityStatus>('/community/status'),
  communityRefresh: () => post<{ available: boolean; pack_count: number }>('/community/refresh'),
  communityLookup: (q: string) => get<{ matches: CommunityPack[] }>('/community/lookup', { q }),
  communityImport: (domain: string) =>
    post<{ ok: boolean; source: CreatedSource }>('/community/import', { domain }),
  communityShare: (id: string) => get<CommunityShare>(`/community/share/${id}`),
  restoreData: (backup_path: string) =>
    post<{ ok: boolean }>('/data/restore', { backup_path }),
}
