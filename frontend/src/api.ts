// In dev: Vite proxies /api → http://127.0.0.1:8766
// In production (Tauri): call FastAPI directly
const BASE = import.meta.env.PROD
  ? 'http://127.0.0.1:8766/api'
  : '/api'

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
  platform: string
  success: boolean
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
  startRefresh: () => post<RefreshStatus>('/refresh/start'),
  refreshStatus: () => get<RefreshStatus>('/refresh/status'),
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
  pinnedNotes: () => get<Note[]>('/notes/pinned'),
  createNote: (body: string, title?: string, note_type?: string) =>
    post<Note>('/notes', { body, title: title ?? null, note_type: note_type ?? 'general' }),
  updateNote: (id: string, patch_data: Partial<Pick<Note, 'title' | 'body_markdown' | 'note_type' | 'pinned'>>) =>
    patch<Note>(`/notes/${id}`, patch_data),
  archiveNote: (id: string) => post<{ ok: boolean }>(`/notes/${id}/archive`),
  deleteNote: (id: string) => del<{ ok: boolean }>(`/notes/${id}`),
}
