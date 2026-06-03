import { useEffect, useRef, useState, useMemo } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'
import { api } from './api'
import type {
  Job, JobDetail, Radar, SourceHealthSummary, Stats, Application, Note,
  OnboardingAnswers, OnboardingState, OnboardingSource
} from './api'

// Open a URL: uses macOS `open` via Tauri command when running in the desktop
// app, falls back to window.open in the browser.
function openExternal(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

// ── Types ─────────────────────────────────────────────────────────────────────

type AppTab = 'jobs' | 'sources' | 'applied' | 'notebook' | 'settings'
type SortCol = 'title' | 'organization' | 'location' | 'application_status' | 'strategic_fit_score' | 'first_seen_at' | 'source'
type SortDir = 'asc' | 'desc'

// ── Constants ─────────────────────────────────────────────────────────────────

const CURRENT_VERSION = '0.1.0'
const VERSION_CHECK_URL = 'https://raw.githubusercontent.com/samclimateman/job-radar-friends/main/latest-version.json'

const JOB_VIEWS = [
  { key: 'best', label: 'Best Fit' },
  { key: 'new', label: 'New' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'closing', label: 'Closing Soon' },
  { key: 'stretch', label: 'Stretch' },
  { key: 'needs_review', label: 'Needs Review' },
  { key: 'excluded', label: 'Excluded' },
]

const STATUS_OPTIONS = [
  { value: 'discovered',  label: 'New' },
  { value: 'reviewing',   label: 'Reviewing' },
  { value: 'shortlist',   label: 'Shortlist' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'applied',     label: 'Applied' },
  { value: 'submitted',   label: 'Submitted' },
  { value: 'rejected',    label: 'Not interested' },
  { value: 'archived',    label: 'Dismissed' },
]

// Map DB status values to user-facing display labels
function displayStatus(status: string) {
  return STATUS_OPTIONS.find(o => o.value === status)?.label
    ?? status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const TABLE_COLS: { key: SortCol; label: string; sortable: boolean }[] = [
  { key: 'title',               label: 'Role',     sortable: true },
  { key: 'location',            label: 'Location', sortable: true },
  { key: 'application_status',  label: 'Status',   sortable: true },
  { key: 'strategic_fit_score', label: 'Fit',      sortable: true },
  { key: 'first_seen_at',       label: 'Seen',     sortable: true },
  { key: 'source',              label: 'Source',   sortable: true },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(score: number) {
  if (score >= 70) return 'bg-emerald-100 text-emerald-800'
  if (score >= 50) return 'bg-sky-100 text-sky-800'
  if (score >= 30) return 'bg-amber-100 text-amber-800'
  return 'bg-slate-100 text-slate-500'
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    shortlist:   'bg-emerald-100 text-emerald-700',
    applied:     'bg-sky-100 text-sky-700',
    submitted:   'bg-sky-100 text-sky-700',
    reviewing:   'bg-violet-100 text-violet-700',
    in_progress: 'bg-amber-100 text-amber-700',
    rejected:    'bg-red-100 text-red-700',
    archived:    'bg-slate-100 text-slate-500',
  }
  return map[status] ?? 'bg-slate-100 text-slate-500'
}

function fmtDate(s: string | null | undefined) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtRefresh(s: string | null | undefined) {
  if (!s) return null
  const d = new Date(s)
  const now = new Date()
  const dMid = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const nMid = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diffDays = Math.round((nMid.getTime() - dMid.getTime()) / 86400000)
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 0) return `today · ${time}`
  if (diffDays === 1) return `yesterday · ${time}`
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  return `${date} · ${time}`
}

function stripHtml(html: string): string {
  const withBreaks = html
    .replace(/<\/p>/gi, '\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<\/h[1-6]>/gi, '\n\n')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/div>/gi, '\n')
  const doc = new DOMParser().parseFromString(withBreaks, 'text/html')
  const text = doc.body.textContent ?? ''
  return text.replace(/\n{3,}/g, '\n\n').trim()
}

function fmtScore(n: number) { return n > 0 ? Math.round(n).toString() : '–' }

function sortValue(job: Job, col: SortCol): string | number {
  switch (col) {
    case 'title':               return job.title.toLowerCase()
    case 'organization':        return job.organization.toLowerCase()
    case 'location':            return (job.location ?? '').toLowerCase()
    case 'application_status':  return job.application_status
    case 'strategic_fit_score': return job.strategic_fit_score
    case 'first_seen_at':       return job.first_seen_at ?? ''
    case 'source':              return job.source
  }
}

function applyFilters(jobs: Job[], search: string, locationFilter: string, blocklist: string[], sortCol: SortCol, sortDir: SortDir): Job[] {
  let out = jobs
  if (search) {
    const q = search.toLowerCase()
    out = out.filter(j =>
      j.title.toLowerCase().includes(q) ||
      j.organization.toLowerCase().includes(q) ||
      (j.location ?? '').toLowerCase().includes(q) ||
      j.source.toLowerCase().includes(q)
    )
  }
  if (locationFilter) {
    out = out.filter(j => (j.location ?? '').toLowerCase().includes(locationFilter.toLowerCase()))
  }
  if (blocklist.length > 0) {
    const phrases = blocklist.map(p => p.toLowerCase())
    out = out.filter(j => {
      const title = j.title.toLowerCase()
      const org = j.organization.toLowerCase()
      return !phrases.some(p => title.includes(p) || org.includes(p))
    })
  }
  return [...out].sort((a, b) => {
    const av = sortValue(a, sortCol)
    const bv = sortValue(b, sortCol)
    const cmp = av < bv ? -1 : av > bv ? 1 : 0
    return sortDir === 'asc' ? cmp : -cmp
  })
}

// ── Update banner ─────────────────────────────────────────────────────────────

function semverGt(a: string, b: string): boolean {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    if ((pa[i] ?? 0) > (pb[i] ?? 0)) return true
    if ((pa[i] ?? 0) < (pb[i] ?? 0)) return false
  }
  return false
}

function UpdateBanner({ version, downloadUrl, onDismiss }: {
  version: string; downloadUrl: string; onDismiss: () => void
}) {
  return (
    <div className="flex items-center gap-3 px-6 py-2.5 bg-amber-50 border-b border-amber-200 text-sm flex-shrink-0">
      <span className="text-amber-800 font-medium">Job Radar v{version} is available.</span>
      <a href={downloadUrl} target="_blank" rel="noreferrer"
        className="text-amber-900 font-semibold underline underline-offset-2 hover:text-amber-950 transition-colors">
        Download now ↗
      </a>
      <button onClick={onDismiss}
        className="ml-auto text-amber-500 hover:text-amber-700 text-xs font-medium transition-colors">
        Dismiss
      </button>
    </div>
  )
}

// ── Stats bar ─────────────────────────────────────────────────────────────────

function StatsBar({ stats, tab, appTitle, onTab, onRefresh, refreshing, onNotebook, onSettings }: {
  stats: Stats | null; tab: AppTab; onTab: (t: AppTab) => void
  appTitle: string; onRefresh: () => void; refreshing: boolean; onNotebook: () => void; onSettings: () => void
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-white border-b border-slate-200 text-sm flex-shrink-0 min-w-0">
      <button onClick={() => onTab('jobs')}
        className="font-semibold text-slate-800 flex items-center gap-1.5 hover:text-slate-600 transition-colors flex-shrink-0 max-w-[160px]">
        <span>📡</span>
        <span className="truncate">{appTitle}</span>
      </button>
      <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5 flex-shrink-0">
        {([['jobs', 'Jobs'], ['applied', 'Applied'], ['sources', 'Sources']] as [AppTab, string][]).map(([t, label]) => (
          <button key={t} onClick={() => onTab(t)}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors
              ${tab === t ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
            {label}
          </button>
        ))}
      </div>
      <div className="w-px h-4 bg-slate-200 flex-shrink-0" />
      <div className="flex items-center gap-3 min-w-0 overflow-hidden">
        {stats ? (
          <>
            <span className="text-slate-600 flex-shrink-0"><strong className="text-slate-800">{stats.jobs}</strong> jobs</span>
            <span className="text-slate-600 flex-shrink-0"><strong className="text-slate-800">{stats.sources}</strong> sources</span>
            {stats.issues > 0 && <button onClick={() => onTab('sources')} className="text-amber-600 font-medium flex-shrink-0 hover:text-amber-800 transition-colors">⚠ {stats.issues} issues</button>}
            {stats.last_refresh && (
              <span className="text-slate-400 text-xs truncate">
                refreshed {fmtRefresh(stats.last_refresh)}
                <span className="ml-2 text-slate-300">v{CURRENT_VERSION}</span>
              </span>
            )}
          </>
        ) : <span className="text-slate-400 text-xs animate-pulse">Loading…</span>}
      </div>
      <div className="ml-auto flex gap-2">
        <button
          onClick={onNotebook}
          className={`px-3 py-1.5 rounded-md border text-xs font-medium transition-colors
            ${tab === 'notebook'
              ? 'border-slate-800 bg-slate-800 text-white'
              : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
          Notebook
        </button>
        <button
          onClick={onSettings}
          className={`px-3 py-1.5 rounded-md border text-xs font-medium transition-colors
            ${tab === 'settings'
              ? 'border-slate-800 bg-slate-800 text-white'
              : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
          Settings
        </button>
        <button onClick={onRefresh} disabled={refreshing}
          className="px-3 py-1.5 rounded-md bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700 disabled:opacity-50 transition-colors">
          {refreshing ? '↻ Refreshing…' : '↻ Refresh Now'}
        </button>
      </div>
    </div>
  )
}

// ── Radar panel ───────────────────────────────────────────────────────────────

function RadarPanel({ radar, onSelectJob, selectedId, onLocationFilter }: {
  radar: Radar | null
  onSelectJob: (id: string) => void
  selectedId: string | null
  onLocationFilter: (loc: string) => void
}) {
  if (!radar) return null
  const total = radar.new.length + radar.reappeared.length + radar.changed.length
  if (total === 0) return null

  return (
    <div className="mx-6 mt-5 rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-700">Today's Radar</h2>
        <span className="text-xs text-slate-400">{total} signal{total !== 1 ? 's' : ''}</span>
      </div>
      <div className="grid grid-cols-3 divide-x divide-slate-100">
        {([
          { label: 'New', items: radar.new, dot: 'bg-emerald-400' },
          { label: 'Reappeared', items: radar.reappeared, dot: 'bg-sky-400' },
          { label: 'Changed', items: radar.changed, dot: 'bg-violet-400' },
        ] as const).map(({ label, items, dot }) => (
          <div key={label} className="px-4 py-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              {label} ({items.length})
            </p>
            {items.length === 0 ? <p className="text-xs text-slate-300 italic">None</p>
              : items.map(j => (
                <button key={j.id} onClick={() => onSelectJob(j.id)}
                  className={`flex items-start gap-2 mb-1.5 w-full text-left rounded px-1 -mx-1 py-0.5 transition-colors group
                    ${j.id === selectedId
                      ? 'bg-sky-50 shadow-[inset_2px_0_0_#38bdf8]'
                      : 'hover:bg-slate-50'}`}>
                  <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-800 truncate">{j.title}</p>
                    <p className="text-xs text-slate-400 truncate flex items-center gap-1">
                      {j.organization}
                      {j.location && (
                        <button
                          onClick={e => { e.stopPropagation(); onLocationFilter(j.location!) }}
                          className="text-slate-300 hover:text-slate-500 group-hover:text-slate-400 transition-colors ml-1"
                          title={`Filter by ${j.location}`}
                        >
                          · {j.location}
                        </button>
                      )}
                    </p>
                  </div>
                  {j.strategic_fit_score > 0 && (
                    <span className="text-xs font-semibold text-slate-400 flex-shrink-0 tabular-nums">
                      {Math.round(j.strategic_fit_score)}
                    </span>
                  )}
                </button>
              ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Location dropdown ─────────────────────────────────────────────────────────

function LocationDropdown({ locations, value, onChange }: {
  locations: string[]
  value: string
  onChange: (loc: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { setOpen(false); setSearch('') }
    }
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false); setSearch('')
      }
    }
    if (open) {
      document.addEventListener('keydown', onKey)
      document.addEventListener('mousedown', onClickOutside)
    }
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClickOutside)
    }
  }, [open])

  const filtered = search
    ? locations.filter(l => l.toLowerCase().includes(search.toLowerCase()))
    : locations

  const label = value ? value : 'All locations'
  const active = !!value

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-colors
          ${active
            ? 'bg-sky-50 border-sky-300 text-sky-700'
            : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'}`}
      >
        {/* Checkbox indicator */}
        <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 transition-colors
          ${active ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}>
          {active && <span className="text-white text-[9px] leading-none">✓</span>}
        </span>
        <span>Location: {label}</span>
        <span className={`text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1.5 w-64 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="p-2 border-b border-slate-100">
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search locations…"
              className="w-full text-xs px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-200"
            />
          </div>

          <div className="max-h-52 overflow-y-auto py-1">
            {filtered.length === 0
              ? <p className="text-xs text-slate-400 px-3 py-2 italic">No matching locations</p>
              : filtered.map(loc => (
                <button
                  key={loc}
                  onClick={() => { onChange(loc === value ? '' : loc); setOpen(false); setSearch('') }}
                  className={`flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs transition-colors
                    ${loc === value ? 'bg-sky-50 text-sky-700' : 'text-slate-700 hover:bg-slate-50'}`}
                >
                  <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0
                    ${loc === value ? 'bg-sky-500 border-sky-500' : 'border-slate-300'}`}>
                    {loc === value && <span className="text-white text-[9px] leading-none">✓</span>}
                  </span>
                  {loc}
                </button>
              ))
            }
          </div>

          {value && (
            <div className="border-t border-slate-100 p-2">
              <button
                onClick={() => { onChange(''); setOpen(false); setSearch('') }}
                className="w-full text-xs text-slate-500 hover:text-slate-700 py-1 transition-colors"
              >
                Clear filter
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Blocklist dropdown ────────────────────────────────────────────────────────

function BlocklistDropdown({ phrases, onAdd, onRemove }: {
  phrases: string[]
  onAdd: (phrase: string) => void
  onRemove: (phrase: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const active = phrases.length > 0

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { setOpen(false); setInput('') }
    }
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false); setInput('')
      }
    }
    if (open) {
      document.addEventListener('keydown', onKey)
      document.addEventListener('mousedown', onClickOutside)
    }
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClickOutside)
    }
  }, [open])

  function handleAdd() {
    const v = input.trim()
    if (!v) return
    onAdd(v)
    setInput('')
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-colors
          ${active
            ? 'bg-red-50 border-red-200 text-red-700'
            : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'}`}
      >
        {active && (
          <span className="w-4 h-4 rounded-full bg-red-500 text-white text-[9px] flex items-center justify-center font-bold leading-none flex-shrink-0">
            {phrases.length}
          </span>
        )}
        <span>Blocklist</span>
        <span className={`text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1.5 w-64 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="p-2 border-b border-slate-100">
            <div className="flex gap-1.5">
              <input
                autoFocus
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAdd()}
                placeholder="Add phrase to block…"
                className="flex-1 text-xs px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-200"
              />
              <button
                onClick={handleAdd}
                disabled={!input.trim()}
                className="text-xs px-2.5 py-1.5 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-700 disabled:opacity-40 transition-colors">
                Add
              </button>
            </div>
          </div>

          <div className="max-h-52 overflow-y-auto py-1">
            {phrases.length === 0
              ? <p className="text-xs text-slate-400 px-3 py-3 italic">No blocked phrases yet</p>
              : phrases.map(p => (
                <div key={p} className="flex items-center justify-between px-3 py-2 hover:bg-slate-50 group">
                  <span className="text-xs text-slate-700 truncate">{p}</span>
                  <button
                    onClick={() => onRemove(p)}
                    className="text-slate-300 hover:text-red-500 transition-colors ml-2 flex-shrink-0 text-xs leading-none">
                    ✕
                  </button>
                </div>
              ))
            }
          </div>

          {active && (
            <div className="border-t border-slate-100 px-3 py-2">
              <p className="text-[10px] text-slate-400">Hiding jobs where title or org matches any phrase</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Sortable header ───────────────────────────────────────────────────────────

function SortTh({ col, label, sortCol, sortDir, onSort }: {
  col: SortCol; label: string; sortCol: SortCol; sortDir: SortDir
  onSort: (col: SortCol) => void
}) {
  const active = col === sortCol
  return (
    <th className="px-4 py-2.5">
      <button
        onClick={() => onSort(col)}
        className={`flex items-center gap-1 text-xs font-semibold uppercase tracking-wide transition-colors
          ${active ? 'text-slate-700' : 'text-slate-400 hover:text-slate-600'}`}
      >
        {label}
        <span className="text-[10px] leading-none">
          {active ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}
        </span>
      </button>
    </th>
  )
}

// ── Job row ───────────────────────────────────────────────────────────────────

function JobRow({ job, selected, onClick, onLocationFilter, onDismiss }: {
  job: Job; selected: boolean; onClick: () => void
  onLocationFilter: (loc: string) => void; onDismiss: (id: string) => void
}) {
  return (
    <tr onClick={onClick}
      className={`border-b border-slate-100 cursor-pointer transition-colors ${selected ? 'bg-sky-50' : 'hover:bg-slate-50'}`}>
      <td className={`px-4 py-3 ${selected ? 'shadow-[inset_2px_0_0_#38bdf8]' : ''}`}>
        <p className={`text-sm leading-snug ${selected ? 'font-semibold text-slate-900' : 'font-medium text-slate-800'}`}>{job.title}</p>
        <p className="text-xs text-slate-400 mt-0.5">{job.organization}</p>
      </td>
      <td className="px-4 py-3">
        {job.location
          ? <button
              onClick={e => { e.stopPropagation(); onLocationFilter(job.location!) }}
              className="text-xs text-slate-500 hover:text-sky-600 hover:underline transition-colors"
              title={`Filter by ${job.location}`}
            >
              {job.location}
            </button>
          : <span className="text-xs text-slate-300">—</span>
        }
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor(job.application_status)}`}>
          {displayStatus(job.application_status)}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`inline-block text-sm font-bold w-10 text-center py-0.5 rounded-lg ${scoreColor(job.strategic_fit_score)}`}>
          {fmtScore(job.strategic_fit_score)}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-slate-400 tabular-nums">{fmtDate(job.first_seen_at)}</td>
      <td className="px-4 py-3 text-xs text-slate-400">{job.source}</td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={e => { e.stopPropagation(); onDismiss(job.id) }}
            title="Hide job — removes from all views"
            className="text-slate-300 hover:text-red-500 hover:bg-red-50 rounded px-1.5 py-0.5 text-xs font-bold leading-none transition-colors border border-transparent hover:border-red-200"
          >✕</button>
          <a href={job.source_url} target="_blank" rel="noreferrer"
            onClick={e => e.stopPropagation()}
            className="text-xs text-sky-600 hover:text-sky-800 hover:underline">Open ↗</a>
        </div>
      </td>
    </tr>
  )
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs text-slate-500 mb-0.5">
        <span>{label}</span><span className="font-medium text-slate-700">{value}</span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-slate-400 rounded-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// ── Description section ───────────────────────────────────────────────────────

const DESC_PREVIEW_CHARS = 600

function DescriptionSection({ raw }: { raw: string }) {
  const [expanded, setExpanded] = useState(false)
  const text = stripHtml(raw) || 'No description captured.'
  const long = text.length > DESC_PREVIEW_CHARS
  const displayed = expanded || !long ? text : text.slice(0, DESC_PREVIEW_CHARS).trimEnd() + '…'

  return (
    <div className="px-5 py-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Description</p>
        {long && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-[11px] text-sky-600 hover:text-sky-800 font-medium transition-colors">
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
      <pre className="text-xs text-slate-600 whitespace-pre-wrap font-sans leading-relaxed">
        {displayed}
      </pre>
      {long && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-2 text-[11px] text-sky-600 hover:text-sky-800 font-medium transition-colors">
          Show full description
        </button>
      )}
    </div>
  )
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function DetailPanel({ jobId, onClose, onStatusChange, onDismiss }: {
  jobId: string; onClose: () => void
  onStatusChange: (id: string, status: string) => void
  onDismiss: (id: string) => void
}) {
  const [detail, setDetail] = useState<JobDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [noteText, setNoteText] = useState('')
  const [noteSaving, setNoteSaving] = useState(false)
  const [noteSaved, setNoteSaved] = useState(false)

  useEffect(() => {
    setLoading(true); setDetail(null); setNoteText(''); setNoteSaved(false)
    api.job(jobId)
      .then(d => { setDetail(d); setNoteText(d.notes ?? ''); setLoading(false) })
      .catch(() => setLoading(false))
  }, [jobId])

  function handleStatus(status: string) {
    if (!detail) return
    api.updateStatus(detail.id, status).then(() => {
      setDetail(prev => prev ? { ...prev, application_status: status } : prev)
      onStatusChange(detail.id, status)
    }).catch(console.error)
  }

  function handleNoteSave() {
    if (!detail) return
    setNoteSaving(true)
    api.updateJobNote(detail.id, noteText)
      .then(() => { setNoteSaved(true); setTimeout(() => setNoteSaved(false), 2000) })
      .catch(console.error)
      .finally(() => setNoteSaving(false))
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between px-5 py-4 border-b border-slate-100">
        <div className="flex-1 min-w-0 pr-4">
          {loading || !detail
            ? <div className="h-5 bg-slate-100 rounded animate-pulse w-3/4 mb-2" />
            : <h2 className="text-base font-semibold text-slate-800 leading-snug">{detail.title}</h2>}
          {detail && (
            <p className="text-sm text-slate-500 mt-0.5">
              {detail.organization}
              {detail.location && <span className="text-slate-400"> · {detail.location}</span>}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {detail && (
            <button
              onClick={() => onDismiss(detail.id)}
              title="Hide job — removes from all views"
              className="text-xs text-slate-400 hover:text-red-500 hover:bg-red-50 border border-transparent hover:border-red-200 rounded px-2 py-1 transition-colors font-medium">
              Hide job
            </button>
          )}
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded transition-colors">✕</button>
        </div>
      </div>

      {loading && <div className="flex-1 flex items-center justify-center text-sm text-slate-400">Loading…</div>}

      {detail && (
        <div className="flex-1 overflow-y-auto">
          {/* Score + status */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex flex-col items-center">
                <span className={`text-2xl font-bold px-3 py-1 rounded-xl ${scoreColor(detail.strategic_fit_score)}`}>
                  {fmtScore(detail.strategic_fit_score)}
                </span>
                <span className="text-[10px] text-slate-400 mt-0.5 tracking-wide">Fit score</span>
              </div>
              <span className={`text-sm px-2.5 py-1 rounded-full font-medium ${statusColor(detail.application_status)}`}>
                {displayStatus(detail.application_status)}
              </span>
              {detail.deadline && <span className="text-xs text-slate-400 ml-auto">Deadline {fmtDate(detail.deadline)}</span>}
            </div>
            <div className="mb-4">
              <ScoreBar label="Location fit" value={detail.geo_score} max={30} />
              <ScoreBar label="Narrative fit" value={detail.narrative_score} />
              <ScoreBar label="Policy fit" value={detail.policy_score} />
            </div>
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Workflow status</p>
              <div className="flex flex-wrap gap-1.5">
                {STATUS_OPTIONS.map(({ value, label }) => (
                  <button key={value} onClick={() => handleStatus(value)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors font-medium
                      ${detail.application_status === value
                        ? 'bg-slate-800 text-white border-slate-800'
                        : 'border-slate-100 text-slate-400 hover:border-slate-300 hover:text-slate-700'}`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Meta */}
          <div className="px-5 py-3 border-b border-slate-100 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            <div className="text-slate-400">Source</div><div className="text-slate-700 font-medium">{detail.source}</div>
            <div className="text-slate-400">First seen</div><div className="text-slate-700">{fmtDate(detail.first_seen_at)}</div>
            <div className="text-slate-400">Last seen</div><div className="text-slate-700">{fmtDate(detail.last_seen_at)}</div>
            {detail.role_type && <><div className="text-slate-400">Role type</div><div className="text-slate-700">{detail.role_type}</div></>}
            {detail.org_type && <><div className="text-slate-400">Org type</div><div className="text-slate-700">{detail.org_type}</div></>}
          </div>

          {/* Actions */}
          <div className="px-5 py-3 border-b border-slate-100">
            <button
              onClick={() => openExternal(detail.source_url)}
              className="text-xs font-semibold text-sky-600 hover:text-sky-800 hover:underline transition-colors">
              Open posting ↗
            </button>
          </div>

          {/* Inline note editor */}
          <div className="px-5 py-4 border-b border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Note</p>
            <textarea
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              placeholder="Add a note about this role…"
              rows={3}
              className="w-full text-sm text-slate-700 border border-slate-200 rounded-lg px-3 py-2
                         focus:outline-none focus:ring-2 focus:ring-sky-200 focus:border-sky-300
                         resize-none placeholder:text-slate-300"
            />
            <div className="flex items-center gap-2 mt-2">
              <button onClick={handleNoteSave} disabled={noteSaving}
                className="text-xs px-3 py-1.5 rounded-md bg-slate-800 text-white font-semibold hover:bg-slate-700 disabled:opacity-50 transition-colors">
                {noteSaving ? 'Saving…' : 'Save note'}
              </button>
              {noteSaved && <span className="text-xs text-emerald-600 font-medium">✓ Saved</span>}
            </div>
          </div>

          {/* Description with show/hide */}
          <DescriptionSection raw={detail.raw_description} />
        </div>
      )}
    </div>
  )
}

// ── Sources view ──────────────────────────────────────────────────────────────

type SourceDraft = {
  organization: string
  url: string
  notes: string
}

function SourcesView() {
  const [health, setHealth] = useState<SourceHealthSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<SourceDraft>({ organization: '', url: '', notes: '' })
  const [busyId, setBusyId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    loadHealth()
  }, [])

  function loadHealth() {
    api.sourceHealth().then(h => { setHealth(h); setLoading(false) }).catch(() => setLoading(false))
  }

  function startEdit(row: SourceHealthSummary['results'][number]) {
    setEditingId(row.source_id)
    setDraft({
      organization: row.org_name === row.url ? '' : row.org_name,
      url: row.url,
      notes: row.notes ?? '',
    })
  }

  function finishAction(message?: string) {
    loadHealth()
    if (message) {
      setNotice(message)
      setTimeout(() => setNotice(null), 3000)
    }
  }

  function saveEdit(sourceId: string) {
    if (!draft.url.trim()) {
      setNotice('Source URL cannot be empty.')
      return
    }
    setBusyId(sourceId)
    api.updateSource(sourceId, {
      organization: draft.organization.trim() || null,
      url: draft.url.trim(),
      notes: draft.notes.trim() || null,
    })
      .then(() => {
        setEditingId(null)
        finishAction('Source saved.')
      })
      .catch(err => setNotice(err.message || 'Could not save source.'))
      .finally(() => setBusyId(null))
  }

  function runSourceAction(sourceId: string, action: 'checked' | 'disable' | 'enable' | 'retry' | 'delete') {
    const labels = {
      checked: 'Source marked checked.',
      disable: 'Source disabled.',
      enable: 'Source enabled.',
      retry: 'Source retry finished.',
      delete: 'Source removed.',
    }
    const call = {
      checked: () => api.markSourceChecked(sourceId),
      disable: () => api.disableSource(sourceId),
      enable: () => api.enableSource(sourceId),
      retry: () => api.retrySource(sourceId),
      delete: () => api.deleteSource(sourceId),
    }[action]
    setBusyId(sourceId)
    call()
      .then(() => finishAction(labels[action]))
      .catch(err => setNotice(err.message || 'Source action failed.'))
      .finally(() => setBusyId(null))
  }

  if (loading) return <div className="flex items-center justify-center py-20 text-sm text-slate-400">Loading…</div>
  if (!health) return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <p className="text-sm text-slate-400">No scans yet — your sources haven't been checked.</p>
      <button onClick={() => { api.startRefresh().catch(console.error); setTimeout(loadHealth, 5000) }}
        className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700 transition-colors">
        Run first refresh
      </button>
    </div>
  )

  const s = health.summary
  const results = health.results.filter(r =>
    !search ||
    r.org_name.toLowerCase().includes(search.toLowerCase()) ||
    r.platform.toLowerCase().includes(search.toLowerCase()) ||
    r.source_id.toLowerCase().includes(search.toLowerCase())
  )
  const issues = results.filter(r => r.manual_review_needed || r.likely_broken_url || !r.success || r.error)
  const ok = results.filter(r => !r.manual_review_needed && !r.likely_broken_url && r.success && !r.error)

  function confBadge(label: string | null) {
    if (!label || label === 'unknown') return 'bg-slate-100 text-slate-500'
    if (label === 'healthy') return 'bg-emerald-100 text-emerald-700'
    if (label === 'broken') return 'bg-red-100 text-red-700'
    if (label === 'degrading') return 'bg-orange-100 text-orange-700'
    return 'bg-amber-100 text-amber-700'
  }

  return (
    <div className="mx-6 mt-5 pb-10">
      <div className="grid grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Sources checked', value: s.sources_attempted, color: 'text-slate-800' },
          { label: 'Succeeded',       value: s.sources_succeeded, color: 'text-emerald-700' },
          { label: 'Failed',          value: s.sources_failed,    color: s.sources_failed > 0 ? 'text-red-600' : 'text-slate-400' },
          { label: 'New jobs',        value: s.total_new,         color: s.total_new > 0 ? 'text-sky-700' : 'text-slate-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white border border-slate-200 rounded-xl px-4 py-3">
            <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="mb-4 flex items-center gap-3">
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Filter sources…"
          className="w-64 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-200 bg-white" />
        {search && <span className="text-xs text-slate-400">{results.length} result{results.length !== 1 ? 's' : ''}</span>}
        {notice && <span className="ml-auto text-xs text-slate-600 bg-white border border-slate-200 rounded-lg px-3 py-2">{notice}</span>}
      </div>

      {issues.length > 0 && (
        <div className="mb-6">
          <h3 className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-2">Issues ({issues.length})</h3>
          <SourceTable rows={issues} confBadge={confBadge}
            editingId={editingId} draft={draft} setDraft={setDraft}
            busyId={busyId} onEdit={startEdit} onCancel={() => setEditingId(null)}
            onSave={saveEdit} onAction={runSourceAction} />
        </div>
      )}

      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
        {issues.length > 0 ? `Working (${ok.length})` : `All Sources (${ok.length})`}
      </h3>
      <SourceTable rows={ok} confBadge={confBadge}
        editingId={editingId} draft={draft} setDraft={setDraft}
        busyId={busyId} onEdit={startEdit} onCancel={() => setEditingId(null)}
        onSave={saveEdit} onAction={runSourceAction} />
    </div>
  )
}

function SourceTable({
  rows, confBadge, editingId, draft, setDraft, busyId,
  onEdit, onCancel, onSave, onAction,
}: {
  rows: SourceHealthSummary['results']
  confBadge: (l: string | null) => string
} & {
  editingId: string | null
  draft: SourceDraft
  setDraft: Dispatch<SetStateAction<SourceDraft>>
  busyId: string | null
  onEdit: (row: SourceHealthSummary['results'][number]) => void
  onCancel: () => void
  onSave: (sourceId: string) => void
  onAction: (sourceId: string, action: 'checked' | 'disable' | 'enable' | 'retry' | 'delete') => void
}) {
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  if (rows.length === 0) return <p className="text-sm text-slate-400 py-4">None.</p>
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-4">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50">
            {['Organisation', 'Platform', 'Jobs', 'Confidence', 'Status', 'Actions'].map(h => (
              <th key={h} className="px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const editing = editingId === r.source_id
            const busy = busyId === r.source_id
            const disabled = r.status === 'disabled' || r.skipped
            return (
              <tr key={r.source_id} className={`border-b border-slate-100 hover:bg-slate-50 ${disabled ? 'bg-slate-50/60' : ''}`}>
                <td className="px-4 py-2.5 min-w-[280px]">
                  {editing ? (
                    <div className="space-y-2">
                      <input value={draft.organization} onChange={e => setDraft(d => ({ ...d, organization: e.target.value }))}
                        placeholder="Organization"
                        className="w-full text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-sky-200" />
                      <input value={draft.url} onChange={e => setDraft(d => ({ ...d, url: e.target.value }))}
                        placeholder="Career page URL"
                        className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-sky-200" />
                      <input value={draft.notes} onChange={e => setDraft(d => ({ ...d, notes: e.target.value }))}
                        placeholder="Notes"
                        className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-sky-200" />
                    </div>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-slate-800">{r.org_name}</p>
                      <a href={r.url} target="_blank" rel="noreferrer"
                        className="text-xs text-sky-600 hover:underline break-all">{r.url}</a>
                      {r.notes && <p className="text-xs text-slate-400 mt-1">{r.notes}</p>}
                    </>
                  )}
                </td>
                <td className="px-4 py-2.5 text-xs text-slate-500">
                  <span className="font-medium">{r.platform}</span>
                  <p className="text-[10px] text-slate-400 mt-1">{r.status}</p>
                </td>
                <td className="px-4 py-2.5 text-sm text-slate-700">
                  {r.jobs_found}
                  {r.jobs_new > 0 && <span className="ml-2 text-xs text-emerald-600 font-medium">+{r.jobs_new}</span>}
                </td>
                <td className="px-4 py-2.5">
                  {r.confidence_label && r.confidence_label !== 'unknown' ? (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${confBadge(r.confidence_label)}`}
                      title={r.confidence_note ?? ''}>
                      {r.confidence_label} {r.confidence_score != null ? `· ${r.confidence_score}` : ''}
                    </span>
                  ) : <span className="text-xs text-slate-300">—</span>}
                </td>
                <td className="px-4 py-2.5">
                  {disabled
                    ? <span className="text-xs text-slate-500 font-medium">Disabled</span>
                    : r.manual_review_needed
                      ? <span className="text-xs text-amber-600 font-medium">Needs manual check</span>
                    : r.likely_broken_url
                      ? <span className="text-xs text-red-600 font-medium">Possible broken URL</span>
                    : r.success
                      ? <span className="text-xs text-emerald-600 font-medium">✓ Working</span>
                      : <span className="text-xs text-red-600" title={r.error ?? ''}>
                          {r.error ? r.error.slice(0, 50) + (r.error.length > 50 ? '…' : '') : 'Needs attention'}
                        </span>}
                </td>
                <td className="px-4 py-2.5">
                  {editing ? (
                    <div className="flex flex-wrap gap-1.5">
                      <button onClick={() => onSave(r.source_id)} disabled={busy}
                        className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 text-white font-semibold hover:bg-slate-700 disabled:opacity-40">
                        Save
                      </button>
                      <button onClick={onCancel}
                        className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50">
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      <button onClick={() => onEdit(r)}
                        className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50">
                        Edit
                      </button>
                      <button onClick={() => onAction(r.source_id, 'checked')} disabled={busy}
                        className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                        Mark checked
                      </button>
                      <button onClick={() => onAction(r.source_id, 'retry')} disabled={busy || disabled}
                        className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                        Retry
                      </button>
                      {disabled ? (
                        <button onClick={() => onAction(r.source_id, 'enable')} disabled={busy}
                          className="text-xs px-2.5 py-1 rounded-lg border border-emerald-200 text-emerald-700 hover:bg-emerald-50 disabled:opacity-40">
                          Enable
                        </button>
                      ) : (
                        <button onClick={() => onAction(r.source_id, 'disable')} disabled={busy}
                          className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                          Disable
                        </button>
                      )}
                      {r.jobs_found === 0 && (
                        pendingDeleteId === r.source_id ? (
                          <div className="flex gap-1">
                            <button onClick={() => { onAction(r.source_id, 'delete'); setPendingDeleteId(null) }} disabled={busy}
                              className="text-xs px-2.5 py-1 rounded-lg bg-red-500 text-white font-semibold hover:bg-red-600 disabled:opacity-40">
                              Confirm
                            </button>
                            <button onClick={() => setPendingDeleteId(null)}
                              className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50">
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button onClick={() => setPendingDeleteId(r.source_id)} disabled={busy}
                            className="text-xs px-2.5 py-1 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-40">
                            Remove
                          </button>
                        )
                      )}
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Applied view ──────────────────────────────────────────────────────────────

const STAGE_OPTIONS = [
  { value: 'screening', label: 'Screening' },
  { value: 'first',     label: '1st interview' },
  { value: 'second',    label: '2nd interview' },
  { value: 'final',     label: 'Final' },
]

const OUTCOME_OPTIONS = [
  { value: 'rejected', label: 'Rejected' },
  { value: 'offer',    label: 'Offer' },
  { value: 'withdrew', label: 'Withdrew' },
  { value: 'ghosted',  label: 'Ghosted' },
]

function outcomeColor(outcome: string | null) {
  if (outcome === 'offer')    return 'bg-emerald-100 text-emerald-700'
  if (outcome === 'rejected') return 'bg-red-100 text-red-700'
  if (outcome === 'withdrew') return 'bg-slate-100 text-slate-500'
  if (outcome === 'ghosted')  return 'bg-amber-100 text-amber-700'
  return ''
}

function AppliedView() {
  const [apps, setApps] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.applications().then(a => { setApps(a); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  function setStage(app: Application, stage: string | null) {
    api.updateAppStage(app.id, stage).then(() => {
      setApps(prev => prev.map(a => a.id === app.id ? { ...a, interview_stage: stage } : a))
    }).catch(console.error)
  }

  function setOutcome(app: Application, outcome: string | null) {
    if (!outcome) return
    api.updateAppOutcome(app.id, outcome).then(() => {
      setApps(prev => prev.map(a => a.id === app.id ? { ...a, outcome } : a))
    }).catch(console.error)
  }

  if (loading) return <div className="flex items-center justify-center py-20 text-sm text-slate-400">Loading…</div>

  if (apps.length === 0) return (
    <div className="flex flex-col items-center justify-center py-20 text-slate-400">
      <p className="text-sm font-medium">No applications tracked yet.</p>
      <p className="text-xs mt-1">Set a job's status to <span className="font-semibold">In Progress</span> or <span className="font-semibold">Applied</span> to start tracking.</p>
    </div>
  )

  const active  = apps.filter(a => !a.outcome)
  const closed  = apps.filter(a => !!a.outcome)

  return (
    <div className="mx-6 mt-5 pb-10">
      {/* Summary chips */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        {[
          { label: 'Total',    value: apps.length,                         color: 'text-slate-800' },
          { label: 'Active',   value: active.length,                       color: 'text-sky-700'   },
          { label: 'Offers',   value: apps.filter(a => a.outcome === 'offer').length,    color: 'text-emerald-700' },
          { label: 'Rejected', value: apps.filter(a => a.outcome === 'rejected').length, color: 'text-red-600'    },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white border border-slate-200 rounded-xl px-4 py-3 min-w-[90px]">
            <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {active.length > 0 && (
        <>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Active ({active.length})</h3>
          <ApplicationTable apps={active} onStage={setStage} onOutcome={setOutcome} />
        </>
      )}

      {closed.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Closed ({closed.length})</h3>
          <ApplicationTable apps={closed} onStage={setStage} onOutcome={setOutcome} />
        </div>
      )}
    </div>
  )
}

function ApplicationTable({ apps, onStage, onOutcome }: {
  apps: Application[]
  onStage: (app: Application, stage: string | null) => void
  onOutcome: (app: Application, outcome: string | null) => void
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-4">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50">
            {['Role', 'Location', 'Fit', 'Applied', 'Stage', 'Outcome', ''].map(h => (
              <th key={h} className="px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {apps.map(app => (
            <tr key={app.id} className="border-b border-slate-100 hover:bg-slate-50">
              <td className="px-4 py-3">
                <p className="text-sm font-medium text-slate-800 leading-snug">{app.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">{app.organization}</p>
              </td>
              <td className="px-4 py-3 text-xs text-slate-500">{app.location ?? '—'}</td>
              <td className="px-4 py-3">
                <span className={`inline-block text-sm font-bold w-10 text-center py-0.5 rounded-lg ${scoreColor(app.strategic_fit_score)}`}>
                  {fmtScore(app.strategic_fit_score)}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-slate-400 tabular-nums">
                {app.submitted_at ? fmtDate(app.submitted_at) : <span className="text-slate-300">—</span>}
              </td>
              <td className="px-4 py-3">
                <select
                  value={app.interview_stage ?? ''}
                  onChange={e => onStage(app, e.target.value || null)}
                  className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
                >
                  <option value="">No stage</option>
                  {STAGE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </td>
              <td className="px-4 py-3">
                {app.outcome ? (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${outcomeColor(app.outcome)}`}>
                    {OUTCOME_OPTIONS.find(o => o.value === app.outcome)?.label ?? app.outcome}
                  </span>
                ) : (
                  <select
                    value=""
                    onChange={e => onOutcome(app, e.target.value || null)}
                    className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
                  >
                    <option value="">Set outcome…</option>
                    {OUTCOME_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                )}
              </td>
              <td className="px-4 py-3 text-right">
                <a href={app.source_url} target="_blank" rel="noreferrer"
                  onClick={e => e.stopPropagation()}
                  className="text-xs text-sky-600 hover:text-sky-800 hover:underline">Open ↗</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Notebook view ─────────────────────────────────────────────────────────────

const NOTE_TYPES = ['general', 'strategy', 'goal', 'organization', 'job', 'application', 'contact', 'brainstorm'] as const

function noteTypeColor(type: string) {
  const map: Record<string, string> = {
    strategy:     'bg-violet-100 text-violet-700',
    goal:         'bg-emerald-100 text-emerald-700',
    application:  'bg-sky-100 text-sky-700',
    job:          'bg-amber-100 text-amber-700',
    organization: 'bg-rose-100 text-rose-700',
    contact:      'bg-teal-100 text-teal-700',
    brainstorm:   'bg-orange-100 text-orange-700',
  }
  return map[type] ?? 'bg-slate-100 text-slate-500'
}

function fmtNoteDate(s: string) {
  const d = new Date(s)
  const now = new Date()
  // Use calendar date diff, not 24-hour diff, so yesterday is always "yesterday"
  const dMidnight = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const nMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diffDays = Math.round((nMidnight.getTime() - dMidnight.getTime()) / 86400000)
  if (diffDays === 0) return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  if (diffDays < 7)  return d.toLocaleDateString('en-GB', { weekday: 'short' })
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function handleNoteBodyKeyDown(
  e: React.KeyboardEvent<HTMLTextAreaElement>,
  value: string,
  onChange: (v: string) => void
) {
  const ta = e.currentTarget
  const start = ta.selectionStart
  const end = ta.selectionEnd

  if (e.key === 'Enter') {
    // Find start of current line
    const lineStart = value.lastIndexOf('\n', start - 1) + 1
    const currentLine = value.slice(lineStart, start)

    // Bullet: "- " or "* "
    const bulletMatch = currentLine.match(/^(\s*)([-*])\s/)
    // Numbered: "1. ", "12. " etc
    const numberedMatch = currentLine.match(/^(\s*)(\d+)\.\s/)

    if (bulletMatch || numberedMatch) {
      const lineContent = currentLine.slice(bulletMatch ? bulletMatch[0].length : numberedMatch![0].length)
      if (!lineContent.trim()) {
        // Empty list item → end the list
        e.preventDefault()
        const prefix = value.slice(0, lineStart)
        const suffix = value.slice(end)
        const newVal = prefix + '\n' + suffix
        onChange(newVal)
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = lineStart + 1
        })
      } else if (bulletMatch) {
        e.preventDefault()
        const indent = bulletMatch[1]
        const bullet = bulletMatch[2]
        const insert = `\n${indent}${bullet} `
        onChange(value.slice(0, start) + insert + value.slice(end))
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = start + insert.length
        })
      } else if (numberedMatch) {
        e.preventDefault()
        const indent = numberedMatch[1]
        const nextNum = parseInt(numberedMatch[2]) + 1
        const insert = `\n${indent}${nextNum}. `
        onChange(value.slice(0, start) + insert + value.slice(end))
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = start + insert.length
        })
      }
    }
  }

  if (e.key === 'Tab') {
    e.preventDefault()
    const insert = e.shiftKey ? '' : '  '
    onChange(value.slice(0, start) + insert + value.slice(end))
    requestAnimationFrame(() => {
      ta.selectionStart = ta.selectionEnd = start + insert.length
    })
  }
}

function NotebookView() {
  const [notes, setNotes]           = useState<Note[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading]       = useState(true)
  const [saving, setSaving]         = useState(false)
  const [saveError, setSaveError]   = useState(false)
  const [editTitle, setEditTitle]   = useState('')
  const [editBody, setEditBody]     = useState('')
  const [editType, setEditType]     = useState('general')
  const [typeFilter, setTypeFilter] = useState('')
  const [search, setSearch]         = useState('')
  const [checked, setChecked]       = useState<Set<string>>(new Set())
  const [trashMode, setTrashMode]   = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const deleteTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setLoading(true)
    setSelectedId(null)
    setChecked(new Set())
    const load = trashMode ? api.trashNotes() : api.notes()
    load.then(n => { setNotes(n); setLoading(false) }).catch(() => setLoading(false))
  }, [trashMode])

  const selected = notes.find(n => n.id === selectedId) ?? null

  useEffect(() => {
    if (selected) {
      setEditTitle(selected.title)
      setEditBody(selected.body_markdown)
      setEditType(selected.note_type)
    }
  }, [selectedId])

  function scheduleSave(id: string, title: string, body: string, type: string) {
    if (saveTimer.current) clearTimeout(saveTimer.current)
    setSaving(true)
    setSaveError(false)
    saveTimer.current = setTimeout(() => {
      api.updateNote(id, { title, body_markdown: body, note_type: type })
        .then(updated => {
          setNotes(prev => prev.map(n => n.id === id ? updated : n))
          setSaving(false)
        })
        .catch(() => { setSaving(false); setSaveError(true) })
    }, 800)
  }

  function handleTitleChange(v: string) {
    setEditTitle(v)
    if (selectedId) scheduleSave(selectedId, v, editBody, editType)
  }

  function handleBodyChange(v: string) {
    setEditBody(v)
    if (selectedId) scheduleSave(selectedId, editTitle, v, editType)
  }

  function handleTypeChange(v: string) {
    setEditType(v)
    if (selectedId) scheduleSave(selectedId, editTitle, editBody, v)
  }

  function handleNewNote() {
    api.createNote('', 'Untitled', 'general').then(note => {
      setNotes(prev => [note, ...prev])
      setSelectedId(note.id)
    }).catch(console.error)
  }

  function handlePin(note: Note) {
    api.updateNote(note.id, { pinned: !note.pinned }).then(updated => {
      setNotes(prev => prev.map(n => n.id === note.id ? updated : n))
    }).catch(console.error)
  }

  function handleArchive(note: Note) {
    if (trashMode) return
    api.archiveNote(note.id).then(() => {
      setNotes(prev => prev.filter(n => n.id !== note.id))
      if (selectedId === note.id) setSelectedId(null)
    }).catch(console.error)
  }

  function handleDelete(note: Note) {
    if (trashMode) return
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      if (deleteTimer.current) clearTimeout(deleteTimer.current)
      deleteTimer.current = setTimeout(() => setDeleteConfirm(false), 3000)
      return
    }
    setDeleteConfirm(false)
    api.deleteNote(note.id).then(() => {
      setNotes(prev => prev.filter(n => n.id !== note.id))
      if (selectedId === note.id) setSelectedId(null)
    }).catch(console.error)
  }

  function handleRestore(note: Note) {
    api.restoreNote(note.id).then(() => {
      setNotes(prev => prev.filter(n => n.id !== note.id))
      if (selectedId === note.id) setSelectedId(null)
    }).catch(console.error)
  }

  function handleCheck(id: string, v: boolean) {
    setChecked(prev => {
      const next = new Set(prev)
      v ? next.add(id) : next.delete(id)
      return next
    })
  }

  function handleArchiveSelected() {
    if (trashMode) return
    const ids = [...checked]
    Promise.all(ids.map(id => api.archiveNote(id))).then(() => {
      setNotes(prev => prev.filter(n => !ids.includes(n.id)))
      if (selectedId && ids.includes(selectedId)) setSelectedId(null)
      setChecked(new Set())
    }).catch(console.error)
  }

  function handleDeleteSelected() {
    if (trashMode) return
    const ids = [...checked]
    Promise.all(ids.map(id => api.deleteNote(id))).then(() => {
      setNotes(prev => prev.filter(n => !ids.includes(n.id)))
      if (selectedId && ids.includes(selectedId)) setSelectedId(null)
      setChecked(new Set())
    }).catch(console.error)
  }

  function handleRestoreSelected() {
    const ids = [...checked]
    Promise.all(ids.map(id => api.restoreNote(id))).then(() => {
      setNotes(prev => prev.filter(n => !ids.includes(n.id)))
      if (selectedId && ids.includes(selectedId)) setSelectedId(null)
      setChecked(new Set())
    }).catch(console.error)
  }

  const filtered = notes.filter(n => {
    if (typeFilter && n.note_type !== typeFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return n.title.toLowerCase().includes(q) || n.body_markdown.toLowerCase().includes(q)
    }
    return true
  })

  const pinned   = filtered.filter(n => n.pinned)
  const unpinned = filtered.filter(n => !n.pinned)

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-3 py-3 border-b border-slate-100 flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1">
            <button onClick={() => setTrashMode(false)}
              className={`px-2 py-1.5 rounded-md text-xs font-semibold transition-colors ${!trashMode ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
              Notes
            </button>
            <button onClick={() => setTrashMode(true)}
              className={`px-2 py-1.5 rounded-md text-xs font-semibold transition-colors ${trashMode ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
              Trash
            </button>
          </div>
          <button onClick={handleNewNote} disabled={trashMode}
            className="w-full px-3 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700 transition-colors">
            + New note
          </button>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search notes…"
            className="w-full text-xs px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-200 bg-white" />
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
            className="w-full text-xs px-2 py-1.5 border border-slate-200 rounded-lg focus:outline-none bg-white text-slate-600">
            <option value="">All types</option>
            {NOTE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && <p className="text-xs text-slate-400 text-center py-6">Loading…</p>}
          {!loading && filtered.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-6">
              {trashMode ? 'Trash is empty.' : 'Nothing here yet — create your first note above.'}
            </p>
          )}
          {pinned.length > 0 && (
            <div className="px-2 pt-3 pb-1">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-1 mb-1">Pinned</p>
              {pinned.map(n => <NoteListItem key={n.id} note={n} selected={n.id === selectedId} checked={checked.has(n.id)} onClick={() => setSelectedId(n.id)} onCheck={handleCheck} />)}
            </div>
          )}
          {unpinned.length > 0 && (
            <div className="px-2 pt-3 pb-2">
              {pinned.length > 0 && <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-1 mb-1">Notes</p>}
              {unpinned.map(n => <NoteListItem key={n.id} note={n} selected={n.id === selectedId} checked={checked.has(n.id)} onClick={() => setSelectedId(n.id)} onCheck={handleCheck} />)}
            </div>
          )}
        </div>

        {checked.size > 0 && (
          <div className="border-t border-slate-200 px-3 py-2 flex items-center gap-2 bg-white">
            <span className="text-xs text-slate-500 mr-auto">{checked.size} selected</span>
            {trashMode ? (
              <button onClick={handleRestoreSelected}
                className="text-xs px-2.5 py-1 rounded-lg border border-emerald-200 text-emerald-600 hover:bg-emerald-50 transition-colors">
                Restore
              </button>
            ) : (
              <>
                <button onClick={handleArchiveSelected}
                  className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-400 hover:text-slate-700 transition-colors">
                  Archive
                </button>
                <button onClick={handleDeleteSelected}
                  className="text-xs px-2.5 py-1 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors">
                  Delete
                </button>
              </>
            )}
            <button onClick={() => setChecked(new Set())}
              className="text-xs text-slate-400 hover:text-slate-600 px-1">x</button>
          </div>
        )}
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            <div className="text-center">
              <p className="text-sm font-medium text-slate-500">
                {trashMode ? 'Deleted notes live here' : 'Your notes live here'}
              </p>
              <p className="text-xs text-slate-400 mt-1 mb-3">
                {trashMode ? 'Restore a note to move it back into the notebook.' : "Track ideas, roles you're watching, contacts, or anything else."}
              </p>
              {!trashMode && (
                <button onClick={handleNewNote}
                  className="text-xs px-4 py-2 rounded-lg bg-slate-800 text-white font-semibold hover:bg-slate-700 transition-colors">
                  + New note
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 px-6 py-3 bg-white border-b border-slate-200">
              <select value={editType} onChange={e => handleTypeChange(e.target.value)} disabled={trashMode}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200 text-slate-600">
                {NOTE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
              </select>
              <div className="ml-auto flex items-center gap-2">
                {saving && <span className="text-xs text-slate-400 animate-pulse">Saving…</span>}
                {!saving && saveError && <span className="text-xs text-red-500 font-medium">Could not save — check your connection</span>}
                {trashMode ? (
                  <button onClick={() => handleRestore(selected)}
                    className="text-xs px-2.5 py-1 rounded-lg border border-emerald-200 text-emerald-600 hover:bg-emerald-50 transition-colors font-medium">
                    Restore
                  </button>
                ) : (
                  <>
                <button onClick={() => handlePin(selected)}
                  title={selected.pinned ? 'Unpin' : 'Pin'}
                  className={`text-xs px-2.5 py-1 rounded-lg border transition-colors font-medium
                    ${selected.pinned ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-600'}`}>
                  {selected.pinned ? '📌 Pinned' : 'Pin'}
                </button>
                <button onClick={() => handleArchive(selected)}
                  className="text-xs px-2.5 py-1 rounded-lg border border-slate-200 text-slate-400 hover:border-red-200 hover:text-red-500 transition-colors">
                  Archive
                </button>
                <button onClick={() => handleDelete(selected)}
                  className={`text-xs px-2.5 py-1 rounded-lg border transition-colors
                    ${deleteConfirm ? 'border-red-300 bg-red-50 text-red-600' : 'border-slate-200 text-slate-400 hover:border-red-200 hover:text-red-500'}`}>
                  {deleteConfirm ? 'Confirm delete' : 'Delete'}
                </button>
                  </>
                )}
              </div>
            </div>
            <div className="flex-1 flex flex-col overflow-hidden px-6 pt-5 pb-4">
              <input
                value={editTitle}
                onChange={e => handleTitleChange(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    document.getElementById('note-body')?.focus()
                  }
                }}
                placeholder="Note title…"
                readOnly={trashMode}
                className="text-xl font-semibold text-slate-800 bg-transparent border-none outline-none placeholder:text-slate-300 mb-2 w-full"
              />
              <div className="flex items-center gap-1 mb-3 border-b border-slate-100 pb-2">
                {[
                  { label: '• Bullet', insert: '- ' },
                  { label: '1. Number', insert: '1. ' },
                ].map(({ label, insert }) => (
                  <button key={label}
                    onMouseDown={e => {
                      e.preventDefault()
                      const ta = document.getElementById('note-body') as HTMLTextAreaElement | null
                      if (!ta) return
                      const pos = ta.selectionStart
                      const val = editBody
                      const lineStart = val.lastIndexOf('\n', pos - 1) + 1
                      const prefix = val.slice(0, lineStart)
                      const rest = val.slice(lineStart)
                      const newVal = prefix + insert + rest
                      handleBodyChange(newVal)
                      requestAnimationFrame(() => {
                        ta.focus()
                        ta.selectionStart = ta.selectionEnd = lineStart + insert.length
                      })
                    }}
                    className="text-xs px-2 py-1 rounded border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors">
                    {label}
                  </button>
                ))}
                <span className="text-[10px] text-slate-300 ml-1">Enter continues lists</span>
              </div>
              <textarea
                id="note-body"
                value={editBody}
                onChange={e => handleBodyChange(e.target.value)}
                onKeyDown={e => handleNoteBodyKeyDown(e, editBody, v => {
                  handleBodyChange(v)
                })}
                readOnly={trashMode}
                className="flex-1 text-sm text-slate-700 bg-transparent border-none outline-none resize-none leading-relaxed"
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function NoteListItem({ note, selected, checked, onClick, onCheck }: {
  note: Note; selected: boolean; checked: boolean
  onClick: () => void; onCheck: (id: string, v: boolean) => void
}) {
  return (
    <div className={`group relative flex items-start rounded-lg mb-0.5 transition-colors
      ${selected ? 'bg-sky-50 shadow-[inset_2px_0_0_#38bdf8]' : 'hover:bg-slate-50'}
      ${checked ? 'bg-slate-100' : ''}`}>
      <div
        className={`absolute left-1 top-2.5 transition-opacity ${checked ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
        onClick={e => { e.stopPropagation(); onCheck(note.id, !checked) }}
      >
        <input
          type="checkbox"
          checked={checked}
          readOnly
          className="w-3 h-3 rounded cursor-pointer accent-slate-600"
        />
      </div>
      <button onClick={onClick}
        className={`flex-1 text-left py-2 pr-2 rounded-lg transition-colors ${checked ? 'pl-5' : 'pl-2 group-hover:pl-5'}`}>
        <p className={`text-xs font-medium truncate ${selected ? 'text-slate-900' : 'text-slate-700'}`}>
          {note.title || <span className="italic text-slate-400">Untitled</span>}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={`text-[10px] px-1.5 py-0 rounded font-medium ${noteTypeColor(note.note_type)}`}>
            {note.note_type}
          </span>
          <span className="text-[10px] text-slate-400 truncate">{fmtNoteDate(note.updated_at)}</span>
        </div>
      </button>
    </div>
  )
}

// ── Onboarding ────────────────────────────────────────────────────────────────

const ONBOARDING_STEPS = [
  'Welcome',
  'Name your Radar',
  'Setup expectations',
  'Current role',
  'Ideal role',
  'Locations',
  'Search criteria',
  'Add sources',
  'Expand your radar',
  'Review sources',
  'Review strategy',
  'First scan',
]

const DEFAULT_SOURCE: OnboardingSource = {
  organization: '',
  url: '',
  notes: '',
  priority: null,
  verified: false,
  llm_suggested: false,
  review_status: '',
}

const DEFAULT_ONBOARDING: OnboardingAnswers = {
  name: '',
  current_role: '',
  ideal_role: '',
  locations: [],
  avoid_constraints: '',
  target_titles: '',
  themes: [],
  custom_themes: '',
  blocked_terms: '',
  role_types_to_avoid: [],
  sources: [{ ...DEFAULT_SOURCE }],
  strategy_summary: '',
}

function normalizeOnboardingAnswers(answers?: OnboardingAnswers | null): OnboardingAnswers {
  const merged = { ...DEFAULT_ONBOARDING, ...(answers ?? {}) }
  return {
    ...merged,
    locations: merged.locations ?? [],
    themes: merged.themes ?? [],
    role_types_to_avoid: merged.role_types_to_avoid ?? [],
    sources: merged.sources?.length ? merged.sources : [{ ...DEFAULT_SOURCE }],
  }
}

const LOCATION_CHIPS = [
  'Brussels', 'Berlin', 'The Hague', 'Amsterdam', 'London',
  'Geneva', 'Zurich', 'Paris', 'Remote Europe', 'Hybrid Europe',
]

const THEME_CHIPS = [
  'International affairs', 'Foreign policy', 'Geopolitics', 'Energy security',
  'Industrial strategy', 'Economic security', 'Critical infrastructure',
  'Climate policy', 'Defence policy', 'European security', 'Strategic foresight',
  'Trade policy', 'Resilience', 'Public-sector strategy',
]

const ROLE_AVOID_CHIPS = [
  'Internships', 'Graduate schemes', 'Junior admin roles', 'Generic communications',
  'Sales / business development', 'Fundraising', 'Technical engineering roles',
  'Software developer roles', 'Roles requiring existing clearance',
  'Roles requiring native-level language skills',
]

function lines(value: string): string[] {
  return value.replace(/,/g, '\n').split('\n').map(v => v.trim()).filter(Boolean)
}

function generatedStrategy(a: OnboardingAnswers) {
  const titles = lines(a.target_titles)
  const themes = [...a.themes, ...lines(a.custom_themes)]
  const blockers = [...lines(a.blocked_terms), ...a.role_types_to_avoid]
  const prioritize = [...titles.slice(0, 6), ...themes.slice(0, 8)].join(', ') || 'roles matching your search criteria'
  const locations = a.locations.join(', ') || 'your preferred locations'
  const downgrade = blockers.slice(0, 10).join(', ') || 'roles outside your stated criteria'
  return [
    `Prioritize ${prioritize} in ${locations}.`,
    `Downgrade or flag ${downgrade}.`,
    'Monitor selected organizations first. Prefer verified vacancies pages. Flag broken or uncertain sources instead of hiding them.',
  ].join('\n\n')
}

function generatedOrgPrompt(a: OnboardingAnswers) {
  const orgs = a.sources
    .filter(s => s.organization.trim() || s.url.trim())
    .map(s => `${s.organization || 'Unknown organization'} — ${s.url || 'URL not provided'}`)
    .join('\n')
  return `I am setting up a personal job radar. Based on the profile below, suggest 15-25 high-quality organizations I should monitor for relevant jobs.

Prioritize relevance over volume.

Current role:
${a.current_role || 'Not specified'}

Ideal job:
${a.ideal_role || 'Not specified'}

Target locations:
${a.locations.join(', ') || 'Not specified'}

Target job titles:
${a.target_titles || 'Not specified'}

Priority themes:
${[...a.themes, ...lines(a.custom_themes)].join(', ') || 'Not specified'}

Roles or terms to avoid:
${[...lines(a.blocked_terms), ...a.role_types_to_avoid].join(', ') || 'Not specified'}

Organizations already added:
${orgs || 'None yet'}

Please return a table with:
1. Organization name
2. Why it fits
3. Country/city
4. Main career page URL
5. Specific vacancies page URL if different
6. Likely job board platform if obvious
7. Priority score from 1-10
8. Whether I should manually verify the URL

Do not invent URLs. If unsure, say "needs manual checking."`
}

function inferSourceStatus(source: OnboardingSource) {
  const url = source.url.trim().toLowerCase()
  if (!url) return 'Missing URL'
  if (!url.startsWith('http://') && !url.startsWith('https://')) return 'Possible broken link'
  if (source.verified) return 'Ready'
  if (source.llm_suggested) return 'Needs manual check'
  if (/\/(careers|jobs|vacancies|join-us|openings|positions|work-with-us)/.test(url)) return 'Looks like a careers page'
  if (/greenhouse|lever|ashby|workable|smartrecruiters|personio/.test(url)) return 'Looks like a job board'
  return 'Likely homepage'
}

function parsePastedSources(raw: string): OnboardingSource[] {
  return raw.split('\n')
    .map(line => line.trim())
    .filter(line => line && !/^[-|:\s]+$/.test(line))
    .map(line => {
      const cells = line.split('|').map(c => c.trim()).filter(Boolean)
      const text = cells.length >= 2 ? cells.join(' ') : line
      const url = text.match(/https?:\/\/[^\s|)]+/)?.[0]?.replace(/[.,;]+$/, '') ?? ''
      const priorityMatch = text.match(/\b(10|[1-9])\b/g)
      const organization = (cells[0] || line.replace(url, '')).replace(/^\d+[\).]\s*/, '').trim()
      return {
        ...DEFAULT_SOURCE,
        organization: organization.slice(0, 120),
        url,
        notes: text.replace(url, '').slice(0, 240),
        priority: priorityMatch ? Number(priorityMatch[priorityMatch.length - 1]) : null,
        llm_suggested: true,
        verified: false,
        review_status: 'Needs manual check',
      }
    })
    .filter(s => s.organization || s.url)
}

function ScanProgress({ onDone }: { onDone: (jobsFound: number) => void }) {
  const [progress, setProgress] = useState<import('./api').RefreshProgress | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    function poll() {
      api.refreshProgress().then(p => {
        setProgress(p)
        if (p.done) {
          onDone(p.jobs_found)
        } else {
          timerRef.current = setTimeout(poll, 2000)
        }
      }).catch(() => { timerRef.current = setTimeout(poll, 3000) })
    }
    poll()
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [])

  if (!progress) return <p className="text-sm text-slate-400 animate-pulse">Starting scan…</p>

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
        {progress.done ? `Scan complete — ${progress.jobs_found} job${progress.jobs_found !== 1 ? 's' : ''} found` : 'Scanning sources…'}
      </p>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        {progress.sources.map(s => (
          <div key={s.source_id} className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-100 last:border-0">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
              s.status === 'done'    ? 'bg-emerald-400' :
              s.status === 'running' ? 'bg-amber-400 animate-pulse' :
              s.status === 'error'   ? 'bg-red-400' :
              'bg-slate-200'
            }`} />
            <span className="text-sm text-slate-700 truncate flex-1">{s.organization}</span>
            <span className="text-xs text-slate-400 flex-shrink-0">
              {s.status === 'done'    ? `${s.new_jobs_found > 0 ? `+${s.new_jobs_found} new` : `${s.jobs_found} jobs`}` :
               s.status === 'running' ? 'scanning…' :
               s.status === 'error'   ? 'failed' :
               'waiting'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ChipToggle({ label, active, onToggle }: { label: string; active: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`px-3 py-1.5 rounded-full border text-xs font-medium transition-colors
        ${active ? 'bg-slate-800 border-slate-800 text-white' : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'}`}
    >
      {label}
    </button>
  )
}

function OnboardingFooter({ step, canContinue, continueLabel, onBack, onContinue, onSkip }: {
  step: number
  canContinue: boolean
  continueLabel?: string
  onBack: () => void
  onContinue: () => void
  onSkip?: () => void
}) {
  const pct = Math.round((step / (ONBOARDING_STEPS.length - 1)) * 100)
  return (
    <div className="border-t border-slate-200 bg-white px-6 py-4 flex items-center gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="font-medium text-slate-700">Step {step} of {ONBOARDING_STEPS.length - 1}</span>
          <span>{ONBOARDING_STEPS[step]}</span>
        </div>
        <div className="mt-2 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-slate-800 rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>
      {onSkip && (
        <button onClick={onSkip} className="px-3 py-2 text-xs font-medium text-slate-500 hover:text-slate-700">
          Skip for now
        </button>
      )}
      <button onClick={onBack} disabled={step === 0}
        className="px-4 py-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors">
        Back
      </button>
      <button onClick={onContinue} disabled={!canContinue}
        className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700 disabled:opacity-40 transition-colors">
        {continueLabel ?? 'Continue'}
      </button>
    </div>
  )
}

function OnboardingWizard({ initialState, onTitle, onDone, onViewSources }: {
  initialState: OnboardingState | null
  onTitle: (title: string) => void
  onDone: () => void
  onViewSources: () => void
}) {
  const [step, setStep] = useState(initialState?.last_step ?? 0)
  const [answers, setAnswers] = useState<OnboardingAnswers>(normalizeOnboardingAnswers(initialState?.answers))
  const [saving, setSaving] = useState(false)
  const [scanStarted, setScanStarted] = useState(false)
  const [scanDone, setScanDone] = useState(false)
  const [sourceResult, setSourceResult] = useState<number | null>(null)
  const [scannableResult, setScannableResult] = useState<number | null>(null)
  const [reviewResult, setReviewResult] = useState<number | null>(null)
  const [llmPaste, setLlmPaste] = useState('')
  const [copiedPrompt, setCopiedPrompt] = useState(false)
  const [autoSaving, setAutoSaving] = useState(false)
  const isFirstRender = useRef(true)
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const title = answers.name.trim() ? `${answers.name.trim()}'s Job Radar` : 'Job Radar'
    onTitle(title)
    document.title = title
  }, [answers.name])

  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return }
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current)
    autosaveTimer.current = setTimeout(async () => {
      setAutoSaving(true)
      try {
        await api.saveOnboarding({ last_step: step, partial: true, answers })
      } finally {
        setAutoSaving(false)
      }
    }, 1500)
    return () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current) }
  }, [answers, step])

  function setAnswer<K extends keyof OnboardingAnswers>(key: K, value: OnboardingAnswers[K]) {
    setAnswers(prev => ({ ...prev, [key]: value }))
  }

  function toggleList(key: 'locations' | 'themes' | 'role_types_to_avoid', value: string) {
    setAnswers(prev => {
      const current = prev[key]
      const next = current.includes(value) ? current.filter(v => v !== value) : [...current, value]
      return { ...prev, [key]: next }
    })
  }

  function updateSource(idx: number, patch: Partial<OnboardingSource>) {
    setAnswers(prev => ({
      ...prev,
      sources: prev.sources.map((s, i) => i === idx ? { ...s, ...patch } : s),
    }))
  }

  function addSourceRow() {
    setAnswers(prev => ({ ...prev, sources: [...prev.sources, { ...DEFAULT_SOURCE }] }))
  }

  function removeSourceRow(idx: number) {
    setAnswers(prev => ({ ...prev, sources: prev.sources.filter((_, i) => i !== idx).length
      ? prev.sources.filter((_, i) => i !== idx)
      : [{ ...DEFAULT_SOURCE }] }))
  }

  async function persist(nextStep = step, partial = false, nextAnswers = answers) {
    setSaving(true)
    try {
      await api.saveOnboarding({ last_step: nextStep, partial, answers: nextAnswers })
    } finally {
      setSaving(false)
    }
  }

  async function go(nextStep: number, partial = false) {
    let nextAnswers = answers
    if (nextStep === 10 && !answers.strategy_summary.trim()) {
      nextAnswers = { ...answers, strategy_summary: generatedStrategy(answers) }
      setAnswers(nextAnswers)
    }
    await persist(nextStep, partial, nextAnswers)
    setStep(nextStep)
  }

  async function completeAndScan() {
    const finalAnswers = {
      ...answers,
      strategy_summary: answers.strategy_summary.trim() || generatedStrategy(answers),
      sources: answers.sources.filter(s => s.url.trim()),
    }
    setAnswers(finalAnswers)
    setSaving(true)
    try {
      const result = await api.completeOnboarding(finalAnswers)
      const scannable = result.sources.filter(s => s.status === 'active').length
      const needsReview = result.sources.filter(s => s.status === 'needs_review').length
      setSourceResult(result.sources_added)
      setScannableResult(scannable)
      setReviewResult(needsReview)
      if (scannable > 0) {
        await api.startRefresh()
        setScanStarted(true)
      }
    } finally {
      setSaving(false)
    }
  }

  const validSources = answers.sources.filter(s => s.url.trim()).length
  const canContinue = (() => {
    if (step === 1) return !!answers.name.trim()
    if (step === 7) return validSources > 0
    if (step === 9) return validSources > 0
    return true
  })()

  return (
    <div className="h-screen bg-slate-50 flex flex-col font-sans">
      <div className="flex-1 flex overflow-hidden">
        <nav className="w-52 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
          <div className="flex-1 overflow-y-auto py-8">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 px-5 mb-2">Setup</p>
            {ONBOARDING_STEPS.map((label, i) => (
              <button
                key={i}
                onClick={() => go(i)}
                className={`w-full text-left px-5 py-2 text-xs transition-colors flex items-center gap-2.5
                  ${i === step
                    ? 'text-slate-900 font-semibold bg-slate-50 border-l-2 border-slate-800'
                    : i < step
                      ? 'text-slate-500 hover:bg-slate-50 border-l-2 border-transparent hover:text-slate-700'
                      : 'text-slate-300 hover:bg-slate-50 border-l-2 border-transparent hover:text-slate-500'}`}
              >
                <span className="w-3 flex-shrink-0 text-[10px] text-emerald-500">
                  {i < step ? '✓' : ''}
                </span>
                {label}
              </button>
            ))}
          </div>
          {autoSaving && (
            <p className="text-[10px] text-slate-400 px-5 py-3 border-t border-slate-100">Saving…</p>
          )}
        </nav>
        <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-8 py-12">
          {step === 0 && (
            <OnboardingScreen title="Job hunting is mostly terrible.">
              <p>Especially when you are looking for something specific.</p>
              <p>That is why I made Job Radar.</p>
              <p>It watches the organizations you care about, tracks new roles, and helps you spot the ones worth your time.</p>
            </OnboardingScreen>
          )}

          {step === 1 && (
            <OnboardingScreen title="What should I call you?">
              <input
                autoFocus
                value={answers.name}
                onChange={e => setAnswer('name', e.target.value)}
                placeholder="Your name"
                className="w-full max-w-md text-lg border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200"
              />
              <p className="text-sm text-slate-400">
                {answers.name.trim() ? `The app will become ${answers.name.trim()}'s Job Radar.` : 'This updates the app title locally.'}
              </p>
            </OnboardingScreen>
          )}

          {step === 2 && (
            <OnboardingScreen title="Set up takes a few minutes.">
              <p>A useful setup takes about 10-15 minutes. A strong setup takes about 30.</p>
              <p>The point is to do the thinking once, so Job Radar can keep watching the right places.</p>
              <div className="grid sm:grid-cols-2 gap-3 pt-2">
                {['Define what you are looking for', 'Add career pages you care about', 'Review the source list', 'Start the first scan'].map(item => (
                  <div key={item} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                    <span className="text-emerald-600 font-semibold mr-2">✓</span>{item}
                  </div>
                ))}
              </div>
            </OnboardingScreen>
          )}

          {step === 3 && (
            <OnboardingScreen title="What is your current job title?">
              <input
                value={answers.current_role}
                onChange={e => setAnswer('current_role', e.target.value)}
                placeholder="Senior Policy Manager, Industrial Innovation & Carbon Capture"
                className="w-full text-base border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200"
              />
            </OnboardingScreen>
          )}

          {step === 4 && (
            <OnboardingScreen title="Describe your ideal job.">
              <textarea
                value={answers.ideal_role}
                onChange={e => setAnswer('ideal_role', e.target.value)}
                rows={7}
                placeholder="Example: I want a policy, strategy, research, operations, or international affairs role focused on the themes I care about."
                className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none leading-relaxed"
              />
            </OnboardingScreen>
          )}

          {step === 5 && (
            <OnboardingScreen title="Where are you job hunting?">
              <div className="flex flex-wrap gap-2">
                {LOCATION_CHIPS.map(loc => (
                  <ChipToggle key={loc} label={loc} active={answers.locations.includes(loc)}
                    onToggle={() => toggleList('locations', loc)} />
                ))}
              </div>
              <input
                value={answers.avoid_constraints}
                onChange={e => setAnswer('avoid_constraints', e.target.value)}
                placeholder="Anything to avoid? Example: no full relocation, no roles requiring existing clearance."
                className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200"
              />
            </OnboardingScreen>
          )}

          {step === 6 && (
            <OnboardingScreen title="What should Job Radar look for?">
              <OnboardingField label="Target job titles">
                <textarea value={answers.target_titles} onChange={e => setAnswer('target_titles', e.target.value)}
                  rows={6} placeholder={'Senior Policy Manager\nStrategy Manager\nProgramme Manager\nAssociate Director'}
                  className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none" />
              </OnboardingField>
              <OnboardingField label="Priority themes">
                <div className="flex flex-wrap gap-2">
                  {THEME_CHIPS.map(theme => (
                    <ChipToggle key={theme} label={theme} active={answers.themes.includes(theme)}
                      onToggle={() => toggleList('themes', theme)} />
                  ))}
                </div>
                <input value={answers.custom_themes} onChange={e => setAnswer('custom_themes', e.target.value)}
                  placeholder="Other themes, comma separated"
                  className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200" />
              </OnboardingField>
              <OnboardingField label="Block filters">
                <textarea value={answers.blocked_terms} onChange={e => setAnswer('blocked_terms', e.target.value)}
                  rows={4} placeholder={'intern\ntrainee\nsales\nnative German\nactive security clearance required'}
                  className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none" />
                <div className="flex flex-wrap gap-2">
                  {ROLE_AVOID_CHIPS.map(role => (
                    <ChipToggle key={role} label={role} active={answers.role_types_to_avoid.includes(role)}
                      onToggle={() => toggleList('role_types_to_avoid', role)} />
                  ))}
                </div>
                <p className="text-xs text-slate-400">Blocked terms downgrade and filter views; excluded jobs remain inspectable.</p>
              </OnboardingField>
            </OnboardingScreen>
          )}

          {step === 7 && (
            <OnboardingScreen title="Add 5-10 organizations you actually care about.">
              <p>Paste the exact page where vacancies appear, not just the homepage. Aim for at least 5. Ten is better.</p>
              <div className="space-y-3">
                {answers.sources.map((source, idx) => (
                  <div key={idx} className="grid grid-cols-[1fr_1.4fr_auto] gap-2 rounded-xl border border-slate-200 bg-white p-3">
                    <input value={source.organization} onChange={e => updateSource(idx, { organization: e.target.value })}
                      placeholder="Organization"
                      className="text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-200" />
                    <input value={source.url} onChange={e => updateSource(idx, { url: e.target.value })}
                      placeholder="https://example.org/careers"
                      className="text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-200" />
                    <button onClick={() => removeSourceRow(idx)}
                      className="px-3 py-2 text-xs font-semibold text-slate-400 hover:text-red-500">
                      Remove
                    </button>
                    <div className="col-span-3 flex items-center gap-3">
                      <input value={source.notes} onChange={e => updateSource(idx, { notes: e.target.value })}
                      placeholder="Notes, priority, or manual check reminder"
                        className="flex-1 text-xs border border-slate-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                      <label className="flex items-center gap-1.5 text-xs text-slate-500 whitespace-nowrap">
                        <input type="checkbox" checked={source.verified}
                          onChange={e => updateSource(idx, { verified: e.target.checked })}
                          className="rounded border-slate-300" />
                        Checked
                      </label>
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={addSourceRow}
                className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50">
                Add organization
              </button>
              <p className="text-xs text-slate-400">Job Radar will detect known boards and flag uncertain pages in source health.</p>
            </OnboardingScreen>
          )}

          {step === 8 && (
            <OnboardingScreen title="Find more organizations worth tracking.">
              <p>Optional: copy this prompt into ChatGPT, Claude, Gemini, or a local model. Paste the results back here and Job Radar will add them to the review list.</p>
              <textarea readOnly value={generatedOrgPrompt(answers)} rows={12}
                className="w-full text-xs border border-slate-200 rounded-xl px-4 py-3 bg-white text-slate-600 focus:outline-none resize-none leading-relaxed" />
              <div className="flex gap-2">
                <button onClick={() => {
                  navigator.clipboard?.writeText(generatedOrgPrompt(answers))
                  setCopiedPrompt(true)
                  setTimeout(() => setCopiedPrompt(false), 1600)
                }}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700">
                  {copiedPrompt ? 'Copied' : 'Copy prompt'}
                </button>
              </div>
              <textarea value={llmPaste} onChange={e => setLlmPaste(e.target.value)} rows={7}
                placeholder="Paste the LLM's organization table or list here..."
                className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none leading-relaxed" />
              <button onClick={() => {
                const parsed = parsePastedSources(llmPaste)
                if (parsed.length === 0) return
                setAnswers(prev => ({
                  ...prev,
                  sources: [...prev.sources.filter(s => s.url.trim() || s.organization.trim()), ...parsed],
                }))
                setLlmPaste('')
              }}
                disabled={!llmPaste.trim()}
                className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                Add pasted organizations
              </button>
              <p className="text-xs text-slate-400">LLM-suggested URLs are marked as needing manual check until you verify them.</p>
            </OnboardingScreen>
          )}

          {step === 9 && (
            <OnboardingScreen title="Review your source list.">
              <p>These are the organizations Job Radar will monitor first. A good source is a real vacancies page, not a vague homepage.</p>
              <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-100">
                    <tr>
                      {['Organization', 'Career page', 'Priority', 'Status', ''].map(h => (
                        <th key={h} className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {answers.sources.filter(s => s.url.trim() || s.organization.trim()).map((source, idx) => {
                      const status = inferSourceStatus(source)
                      const realIdx = answers.sources.indexOf(source)
                      return (
                        <tr key={`${source.organization}-${idx}`} className="border-b border-slate-100">
                          <td className="px-3 py-2">
                            <input value={source.organization} onChange={e => updateSource(realIdx, { organization: e.target.value })}
                              className="w-full text-sm border border-transparent hover:border-slate-200 focus:border-slate-300 rounded px-2 py-1 focus:outline-none" />
                            {source.llm_suggested && <span className="text-[10px] text-violet-500 font-medium">LLM suggested</span>}
                          </td>
                          <td className="px-3 py-2">
                            <input value={source.url} onChange={e => updateSource(realIdx, { url: e.target.value })}
                              className="w-full text-xs border border-transparent hover:border-slate-200 focus:border-slate-300 rounded px-2 py-1 focus:outline-none" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min={1} max={10} value={source.priority ?? ''}
                              onChange={e => updateSource(realIdx, { priority: e.target.value ? Number(e.target.value) : null })}
                              className="w-16 text-xs border border-slate-200 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                          </td>
                          <td className="px-3 py-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              status === 'Ready' || status.includes('job board') || status.includes('careers')
                                ? 'bg-emerald-100 text-emerald-700'
                                : status === 'Missing URL' || status.includes('broken')
                                  ? 'bg-red-100 text-red-700'
                                  : 'bg-amber-100 text-amber-700'
                            }`}>
                              {status}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right whitespace-nowrap">
                            {source.url && <a href={source.url} target="_blank" rel="noreferrer" className="text-xs text-sky-600 hover:underline mr-3">Open</a>}
                            <button onClick={() => updateSource(realIdx, { verified: !source.verified })}
                              className="text-xs text-slate-600 hover:text-slate-900 font-medium">
                              {source.verified ? 'Uncheck' : 'Mark checked'}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-400">Unchecked LLM sources will be saved for manual review instead of silently failing.</p>
            </OnboardingScreen>
          )}

          {step === 10 && (
            <OnboardingScreen title="Review your Radar strategy.">
              <p>Here is how Job Radar will interpret your search. Edit anything that feels off.</p>
              <textarea
                value={answers.strategy_summary || generatedStrategy(answers)}
                onChange={e => setAnswer('strategy_summary', e.target.value)}
                rows={10}
                className="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none leading-relaxed"
              />
            </OnboardingScreen>
          )}

          {step === 11 && (
            <OnboardingScreen title={scanDone ? 'First scan complete.' : scanStarted ? 'Scanning your sources.' : 'Onboarding complete.'}>
              {!scanStarted && (
                <p>
                  {sourceResult !== null && scannableResult === 0
                    ? 'Your sources were saved, but they need manual review before Job Radar can scan them.'
                    : 'Ready to start your first scan.'}
                </p>
              )}
              {scanStarted && !scanDone && (
                <ScanProgress onDone={jobsFound => {
                  setScanDone(true)
                  setSourceResult(prev => prev ?? jobsFound)
                }} />
              )}
              {scanDone && (
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-slate-500">Sources added</span><span className="font-semibold text-slate-800">{sourceResult ?? 0}</span></div>
                    {scannableResult !== null && <div className="flex justify-between"><span className="text-slate-500">Scannable</span><span className="font-semibold text-slate-800">{scannableResult}</span></div>}
                    {reviewResult !== null && reviewResult > 0 && <div className="flex justify-between"><span className="text-slate-500">Need manual check</span><span className="font-semibold text-amber-700">{reviewResult}</span></div>}
                  </div>
                  <button onClick={onViewSources}
                    className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50">
                    View source health
                  </button>
                </div>
              )}
            </OnboardingScreen>
          )}
        </div>
        </div>
      </div>

      <OnboardingFooter
        step={step}
        canContinue={canContinue && !saving && !(step === 11 && scanStarted && !scanDone)}
        continueLabel={step === 0 ? 'Start setup' : step === 2 ? "I'm ready" : step === 11 ? (scanDone ? 'Go to dashboard' : scanStarted ? 'Scanning…' : 'Start first scan') : 'Continue'}
        onBack={() => step > 0 && go(step - 1)}
        onContinue={() => {
          if (step === 11) {
            if (scanDone) onDone()
            else if (!scanStarted) completeAndScan()
          } else {
            go(step + 1)
          }
        }}
        onSkip={step > 2 && step < 8 ? () => go(step + 1, true) : step === 8 ? () => go(9, true) : step === 2 ? () => go(7, true) : undefined}
      />
    </div>
  )
}

function OnboardingScreen({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">First-run setup</p>
        <h1 className="text-3xl font-semibold text-slate-900 tracking-normal">{title}</h1>
      </div>
      <div className="space-y-4 text-base text-slate-600 leading-relaxed">
        {children}
      </div>
    </div>
  )
}

function OnboardingField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      {children}
    </div>
  )
}

// ── Settings view ─────────────────────────────────────────────────────────────

function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-700 pb-2 border-b border-slate-100">{title}</h3>
      <div className="space-y-5">{children}</div>
    </div>
  )
}

function SettingsField({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
      {children}
    </div>
  )
}

function SettingsView({ onboarding, onSaved }: { onboarding: OnboardingState | null; onSaved: () => void }) {
  const [answers, setAnswers] = useState<OnboardingAnswers>(normalizeOnboardingAnswers(onboarding?.answers))
  const [saving, setSaving] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'saved' | 'error'>('idle')

  useEffect(() => {
    setAnswers(normalizeOnboardingAnswers(onboarding?.answers))
  }, [onboarding])

  function setAnswer<K extends keyof OnboardingAnswers>(key: K, value: OnboardingAnswers[K]) {
    setAnswers(prev => ({ ...prev, [key]: value }))
  }

  function toggleList(key: 'locations' | 'themes' | 'role_types_to_avoid', value: string) {
    setAnswers(prev => {
      const current = prev[key]
      const next = current.includes(value) ? current.filter(v => v !== value) : [...current, value]
      return { ...prev, [key]: next }
    })
  }

  async function handleSave() {
    setSaving(true)
    setSaveState('idle')
    try {
      const finalAnswers = {
        ...answers,
        strategy_summary: answers.strategy_summary.trim() || generatedStrategy(answers),
      }
      await api.completeOnboarding(finalAnswers)
      await api.saveOnboarding({ answers: finalAnswers })
      setSaveState('saved')
      setTimeout(() => setSaveState('idle'), 2500)
      onSaved()
    } catch {
      setSaveState('error')
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full text-sm border border-slate-200 rounded-xl px-4 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-sky-200'

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-8 py-8 space-y-10">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Settings</h2>
          <p className="text-sm text-slate-500 mt-1">Update your criteria at any time. Changes are applied to scoring and filtering immediately on save.</p>
        </div>

        <SettingsSection title="Identity">
          <SettingsField label="Your name">
            <input value={answers.name} onChange={e => setAnswer('name', e.target.value)}
              className={`${inputCls} max-w-xs`} />
          </SettingsField>
          <SettingsField label="Current role">
            <input value={answers.current_role} onChange={e => setAnswer('current_role', e.target.value)}
              className={inputCls} />
          </SettingsField>
          <SettingsField label="Ideal job">
            <textarea value={answers.ideal_role} onChange={e => setAnswer('ideal_role', e.target.value)}
              rows={4} className={`${inputCls} resize-none leading-relaxed`} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Where you're looking">
          <SettingsField label="Locations">
            <div className="flex flex-wrap gap-2">
              {LOCATION_CHIPS.map(loc => (
                <ChipToggle key={loc} label={loc} active={answers.locations.includes(loc)}
                  onToggle={() => toggleList('locations', loc)} />
              ))}
            </div>
          </SettingsField>
          <SettingsField label="Location constraints" hint="Anything to avoid, e.g. no full relocation.">
            <input value={answers.avoid_constraints} onChange={e => setAnswer('avoid_constraints', e.target.value)}
              className={inputCls} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="What you're looking for">
          <SettingsField label="Target job titles">
            <textarea value={answers.target_titles} onChange={e => setAnswer('target_titles', e.target.value)}
              rows={5} placeholder={"Senior Policy Manager\nStrategy Manager\nProgramme Manager"}
              className={`${inputCls} resize-none`} />
          </SettingsField>
          <SettingsField label="Priority themes">
            <div className="flex flex-wrap gap-2 mb-2">
              {THEME_CHIPS.map(theme => (
                <ChipToggle key={theme} label={theme} active={answers.themes.includes(theme)}
                  onToggle={() => toggleList('themes', theme)} />
              ))}
            </div>
            <input value={answers.custom_themes} onChange={e => setAnswer('custom_themes', e.target.value)}
              placeholder="Other themes, comma separated" className={inputCls} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Block filters">
          <SettingsField label="Terms to block" hint="Blocked terms downgrade and filter views; excluded jobs remain inspectable.">
            <textarea value={answers.blocked_terms} onChange={e => setAnswer('blocked_terms', e.target.value)}
              rows={4} placeholder={"intern\ntrainee\nsales"}
              className={`${inputCls} resize-none`} />
          </SettingsField>
          <SettingsField label="Role types to avoid">
            <div className="flex flex-wrap gap-2">
              {ROLE_AVOID_CHIPS.map(role => (
                <ChipToggle key={role} label={role} active={answers.role_types_to_avoid.includes(role)}
                  onToggle={() => toggleList('role_types_to_avoid', role)} />
              ))}
            </div>
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Radar strategy">
          <SettingsField label="Strategy summary" hint="Used to score and rank jobs. Edit directly or regenerate from your criteria above.">
            <textarea value={answers.strategy_summary} onChange={e => setAnswer('strategy_summary', e.target.value)}
              rows={6} className={`${inputCls} resize-none leading-relaxed`} />
            <button onClick={() => setAnswer('strategy_summary', generatedStrategy(answers))}
              className="text-xs text-sky-600 hover:text-sky-800 font-medium transition-colors mt-1">
              Regenerate from criteria
            </button>
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Sources">
          <p className="text-sm text-slate-500">Add, edit, or remove monitored career pages in the <strong className="text-slate-700">Sources</strong> tab.</p>
        </SettingsSection>

        <div className="pt-2 flex items-center gap-4">
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2.5 rounded-xl bg-slate-800 text-white text-sm font-semibold hover:bg-slate-700 disabled:opacity-40 transition-colors">
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          {saveState === 'saved' && <span className="text-sm text-emerald-600 font-medium">✓ Saved</span>}
          {saveState === 'error' && <span className="text-sm text-red-500">Save failed — try again</span>}
        </div>
      </div>
    </div>
  )
}

function SetupQualityBanner({ onboarding, stats, refreshing, onGoToSources }: {
  onboarding: OnboardingState | null
  stats: Stats | null
  refreshing: boolean
  onGoToSources: () => void
}) {
  if (!onboarding?.completed) return null
  const answers = onboarding.answers
  const sources = answers.sources.filter(s => s.url.trim())
  const verified = sources.filter(s => s.verified).length
  const unchecked = Math.max(0, sources.length - verified)
  const blockConfigured = lines(answers.blocked_terms).length + answers.role_types_to_avoid.length > 0
  const strategyConfigured = !!answers.strategy_summary.trim()
  const quality =
    sources.length >= 10 && verified >= 5 && blockConfigured && strategyConfigured ? 'Strong'
    : sources.length >= 5 && strategyConfigured ? 'Good'
    : 'Getting started'
  const qualityClass =
    quality === 'Strong' ? 'text-emerald-700 bg-emerald-100'
    : quality === 'Good' ? 'text-sky-700 bg-sky-100'
    : 'text-amber-700 bg-amber-100'

  return (
    <div className="mx-6 mt-5 rounded-xl border border-slate-200 bg-white px-5 py-4">
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${qualityClass}`}>
          Radar: {quality}
        </span>
        <span className="text-xs text-slate-500"><strong className="text-slate-800">{sources.length}</strong> sources added</span>
        <span className="text-xs text-slate-500"><strong className="text-slate-800">{verified}</strong> verified</span>
        {unchecked > 0 && (
          <button onClick={onGoToSources} className="text-xs text-amber-600 hover:text-amber-800 transition-colors">
            <strong>{unchecked}</strong> need manual check →
          </button>
        )}
        <span className="text-xs text-slate-500">{blockConfigured ? 'Block filters on' : 'No block filters'}</span>
        <span className="text-xs text-slate-500">{refreshing ? 'Scanning…' : stats?.last_refresh ? `Last scan ${new Date(stats.last_refresh).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}` : 'Not yet scanned'}</span>
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [stats, setStats]               = useState<Stats | null>(null)
  const [radar, setRadar]               = useState<Radar | null>(null)
  const [jobs, setJobs]                 = useState<Job[]>([])
  const [onboarding, setOnboarding]     = useState<OnboardingState | null>(null)
  const [onboardingLoaded, setOnboardingLoaded] = useState(false)
  const [appTitle, setAppTitle]         = useState('Job Radar')
  const [view, setView]                 = useState('best')
  const [search, setSearch]             = useState('')
  const [locationFilter, setLocation]   = useState('')
  const [blocklist, setBlocklist]       = useState<string[]>([])
  const [sortCol, setSortCol]           = useState<SortCol>('strategic_fit_score')
  const [sortDir, setSortDir]           = useState<SortDir>('desc')
  const [selectedId, setSelectedId]     = useState<string | null>(null)
  const [refreshing, setRefreshing]     = useState(false)
  const [tab, setTab]                   = useState<AppTab>('jobs')
  const [updateInfo, setUpdateInfo]     = useState<{ version: string; download_url: string } | null>(null)
  const [updateDismissed, setUpdateDismissed] = useState(false)
  const [undoJob, setUndoJob]           = useState<{ id: string; title: string } | null>(null)
  const [serverError, setServerError]   = useState(false)
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function loadJobs(v = view) {
    api.jobs(v).then(setJobs).catch(console.error)
  }

  useEffect(() => {
    api.stats().then(setStats).catch(() => setServerError(true))
    api.radar().then(setRadar).catch(console.error)
    api.getBlocklist().then(setBlocklist).catch(console.error)
    api.onboarding()
      .then(state => {
        setOnboarding(state)
        if (state.answers.name.trim()) setAppTitle(`${state.answers.name.trim()}'s Job Radar`)
      })
      .catch(console.error)
      .finally(() => setOnboardingLoaded(true))
    loadJobs()
    fetch(VERSION_CHECK_URL)
      .then(r => r.json())
      .then(data => { if (semverGt(data.version, CURRENT_VERSION)) setUpdateInfo(data) })
      .catch(() => {})
  }, [])

  useEffect(() => { loadJobs() }, [view])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName
      if (e.key === 'Escape') setSelectedId(null)
      if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
        e.preventDefault()
        document.getElementById('job-search')?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function handleSort(col: SortCol) {
    if (col === sortCol) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir(col === 'strategic_fit_score' ? 'desc' : 'asc') }
  }

  function handleRefresh() {
    setRefreshing(true)
    api.startRefresh().catch(console.error)
    function poll() {
      api.refreshStatus().then(s => {
        if (s.done || !s.running) {
          setRefreshing(false)
          api.stats().then(setStats)
          api.radar().then(setRadar)
          loadJobs()
        } else { pollRef.current = setTimeout(poll, 2000) }
      }).catch(() => setRefreshing(false))
    }
    pollRef.current = setTimeout(poll, 2000)
  }

  function handleStatusChange(id: string, status: string) {
    setJobs(prev => prev.map(j => j.id === id ? { ...j, application_status: status } : j))
  }

  function handleDismiss(id: string) {
    const job = jobs.find(j => j.id === id)
    api.updateStatus(id, 'archived').then(() => {
      setJobs(prev => prev.filter(j => j.id !== id))
      if (selectedId === id) setSelectedId(null)
      if (undoTimer.current) clearTimeout(undoTimer.current)
      setUndoJob(job ? { id, title: job.title } : null)
      undoTimer.current = setTimeout(() => setUndoJob(null), 5000)
    }).catch(console.error)
  }

  function handleUndoDismiss() {
    if (!undoJob) return
    api.updateStatus(undoJob.id, 'discovered').then(() => {
      setUndoJob(null)
      if (undoTimer.current) clearTimeout(undoTimer.current)
      loadJobs()
    }).catch(console.error)
  }

  function handleLocationFilter(loc: string) {
    setLocation(prev => prev === loc ? '' : loc)
  }

  function handleAddPhrase(phrase: string) {
    api.addToBlocklist(phrase).then(setBlocklist).catch(console.error)
  }

  function handleRemovePhrase(phrase: string) {
    api.removeFromBlocklist(phrase).then(setBlocklist).catch(console.error)
  }

  function refreshAppData() {
    api.stats().then(setStats).catch(console.error)
    api.radar().then(setRadar).catch(console.error)
    api.getBlocklist().then(setBlocklist).catch(console.error)
    loadJobs()
  }

  function finishOnboarding(targetTab: AppTab = 'jobs') {
    api.onboarding().then(setOnboarding).catch(console.error)
    refreshAppData()
    setTab(targetTab)
    setSelectedId(null)
  }

  const filtered = useMemo(
    () => applyFilters(jobs, search, locationFilter, blocklist, sortCol, sortDir),
    [jobs, search, locationFilter, blocklist, sortCol, sortDir]
  )

  const panelOpen = selectedId !== null && tab === 'jobs'
  const shouldShowOnboarding = onboardingLoaded && onboarding !== null && !onboarding.completed

  if (shouldShowOnboarding) {
    return (
      <OnboardingWizard
        initialState={onboarding}
        onTitle={setAppTitle}
        onDone={() => finishOnboarding('jobs')}
        onViewSources={() => finishOnboarding('sources')}
      />
    )
  }

  return (
    <div className="h-screen bg-slate-50 font-sans flex flex-col overflow-hidden">
      <StatsBar stats={stats} tab={tab} appTitle={appTitle}
        onTab={t => { setTab(t); setSelectedId(null) }}
        onRefresh={handleRefresh} refreshing={refreshing}
        onNotebook={() => { setTab('notebook'); setSelectedId(null) }}
        onSettings={() => { setTab('settings'); setSelectedId(null) }} />
      {serverError && (
        <div className="flex items-center gap-3 px-6 py-2.5 bg-red-50 border-b border-red-200 text-sm flex-shrink-0">
          <span className="text-red-700 font-medium">Job Radar can't reach its backend. Try restarting the app.</span>
          <button onClick={() => window.location.reload()} className="ml-auto text-red-600 hover:text-red-800 text-xs font-medium transition-colors">Reload</button>
        </div>
      )}
      {updateInfo && !updateDismissed && (
        <UpdateBanner version={updateInfo.version} downloadUrl={updateInfo.download_url}
          onDismiss={() => setUpdateDismissed(true)} />
      )}
      {undoJob && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 flex items-center gap-4 bg-slate-800 text-white text-sm px-5 py-3 rounded-xl shadow-lg">
          <span className="truncate max-w-[260px]">"{undoJob.title}" hidden</span>
          <button onClick={handleUndoDismiss} className="text-sky-300 hover:text-sky-100 font-semibold transition-colors flex-shrink-0">Undo</button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <div className={`flex-1 ${tab === 'notebook' ? 'overflow-hidden flex' : 'overflow-y-auto'} ${tab === 'settings' ? 'overflow-y-auto' : ''}`}>
          {tab === 'jobs' && (
            <>
              {stats && stats.sources === 0 && (
                <div className="mx-6 mt-5 rounded-xl border border-sky-200 bg-sky-50 px-5 py-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-sky-900">No sources yet</p>
                    <p className="text-xs text-sky-700 mt-0.5">Add career pages to start monitoring jobs. Use the Settings page to add sources and set your strategy.</p>
                  </div>
                  <a href="http://127.0.0.1:8767/wizard" target="_blank" rel="noreferrer"
                    className="flex-shrink-0 ml-4 px-4 py-2 rounded-lg bg-sky-600 text-white text-xs font-semibold hover:bg-sky-700 transition-colors">
                    Get started →
                  </a>
                </div>
              )}
              <SetupQualityBanner onboarding={onboarding} stats={stats} refreshing={refreshing} onGoToSources={() => setTab('sources')} />
              <RadarPanel radar={radar} selectedId={selectedId} onSelectJob={id => { setSelectedId(id); setTab('jobs') }}
                onLocationFilter={handleLocationFilter} />

              <div className="mx-6 mt-5 pb-10">
                {/* Controls row */}
                <div className="flex items-center gap-3 mb-4 flex-wrap">
                  <div className="flex gap-1 bg-white border border-slate-200 rounded-xl p-1">
                    {JOB_VIEWS.map(v => (
                      <button key={v.key}
                        onClick={() => { setView(v.key); setSearch(''); setLocation('') }}
                        className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors
                          ${view === v.key ? 'bg-slate-800 text-white' : 'text-slate-500 hover:text-slate-700'}`}>
                        {v.label}
                      </button>
                    ))}
                  </div>

                  <div className="ml-auto flex items-center gap-2">
                    <LocationDropdown
                      locations={[...new Set(jobs.map(j => j.location).filter(Boolean) as string[])].sort()}
                      value={locationFilter}
                      onChange={loc => setLocation(loc)}
                    />
                    <BlocklistDropdown
                      phrases={blocklist}
                      onAdd={handleAddPhrase}
                      onRemove={handleRemovePhrase}
                    />

                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none">🔍</span>
                      <input
                        id="job-search"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        placeholder="Search… (/)"
                        className="pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-xl bg-white
                                   focus:outline-none focus:ring-2 focus:ring-sky-200 w-52"
                      />
                      {search && (
                        <button onClick={() => setSearch('')}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs">✕</button>
                      )}
                    </div>
                    <span className="text-xs text-slate-400 tabular-nums">
                      Showing {filtered.length} of {jobs.length}
                    </span>
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50">
                        {TABLE_COLS.map(({ key, label }) => (
                          <SortTh key={key} col={key} label={label}
                            sortCol={sortCol} sortDir={sortDir} onSort={handleSort} />
                        ))}
                        <th className="px-4 py-2.5 text-[10px] font-semibold text-slate-300 uppercase tracking-wide text-right">Hide</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length === 0
                        ? <tr><td colSpan={7} className="px-4 py-12 text-center">
                            <p className="text-sm text-slate-400">
                              {search || locationFilter ? 'No results for current filters.' : 'No jobs in this view.'}
                            </p>
                            {!search && !locationFilter && (
                              <p className="text-xs text-slate-300 mt-1">
                                {view === 'best' ? 'Run a refresh to scan your sources, or add sources in Settings.' : 'Try a different view or run a refresh.'}
                              </p>
                            )}
                          </td></tr>
                        : filtered.map(j => (
                          <JobRow key={j.id} job={j} selected={j.id === selectedId}
                            onClick={() => setSelectedId(prev => prev === j.id ? null : j.id)}
                            onLocationFilter={handleLocationFilter}
                            onDismiss={handleDismiss} />
                        ))
                      }
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
          {tab === 'sources' && <SourcesView />}
          {tab === 'applied' && <AppliedView />}
          {tab === 'notebook' && <NotebookView />}
          {tab === 'settings' && (
            <SettingsView
              onboarding={onboarding}
              onSaved={() => {
                api.onboarding().then(setOnboarding).catch(console.error)
                api.getBlocklist().then(setBlocklist).catch(console.error)
                refreshAppData()
              }}
            />
          )}
        </div>

        {panelOpen && (
          <div className="w-[440px] flex-shrink-0 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
            <DetailPanel jobId={selectedId!} onClose={() => setSelectedId(null)} onStatusChange={handleStatusChange} onDismiss={handleDismiss} />
          </div>
        )}
      </div>
    </div>
  )
}
