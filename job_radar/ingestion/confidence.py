"""Source confidence scoring derived from scan history.

Scoring model mirrors career-ops/ingestion/confidence.py: start at 100,
apply named deductions, band into label. Keeping both tools aligned means
the same thresholds and logic apply — differences only where SQLite vs
Postgres require it.

Score bands:
  healthy   80–100  — consistently successful, recent, plausible job counts
  watch     60–79   — mostly fine, minor issues
  degrading 40–59   — intermittent failures or repeated zero-job runs
  broken     0–39   — frequent failures, stale, or never worked
"""

from __future__ import annotations

from dataclasses import dataclass, field

from job_radar.db.client import execute

_WINDOW = 10          # runs to fetch for history
_BROKEN_DAYS = 14     # no success in this many days → broken
_DEGRADING_DAYS = 7   # no success in this many days → at least degrading


@dataclass
class ConfidenceResult:
    score:               int
    label:               str          # healthy | watch | degrading | broken | manual | unknown
    warnings:            list[str] = field(default_factory=list)
    suggested_action:    str = ""
    recent_success_rate: float = 0.0  # 0.0–1.0 over last 5 runs
    days_since_success:  int | None = None
    latest_jobs:         int = 0
    avg_jobs:            float = 0.0


def _label(score: int) -> str:
    if score >= 80:
        return "healthy"
    if score >= 60:
        return "watch"
    if score >= 40:
        return "degrading"
    return "broken"


def _suggested_action(label: str) -> str:
    if label == "healthy":
        return "No action needed."
    if label == "watch":
        return "Monitor over the next few runs."
    if label == "degrading":
        return "Test source manually — check the careers page URL."
    return "Source likely broken — verify URL or disable."


def compute_confidence(source_id: str, status: str) -> ConfidenceResult:
    if status in ("needs_review", "disabled"):
        label = "manual" if status == "needs_review" else "unknown"
        return ConfidenceResult(score=0, label=label,
                                suggested_action=f"Source is {status.replace('_', ' ')}.")

    runs = execute(
        """
        SELECT status, jobs_found, error,
               CAST(julianday('now') - julianday(finished_at) AS INTEGER) AS days_ago
        FROM source_runs
        WHERE source_id = ?
          AND finished_at IS NOT NULL
        ORDER BY finished_at DESC
        LIMIT ?
        """,
        (source_id, _WINDOW),
    )

    if not runs:
        return ConfidenceResult(score=0, label="unknown",
                                warnings=["No scan history yet."],
                                suggested_action="Run ingestion to populate history.")

    score = 100
    warnings: list[str] = []

    # ── Recent success rate (last 5 runs) ────────────────────────────────────
    recent = runs[:5]
    successes_5 = sum(1 for r in recent if r["status"] == "success")
    recent_success_rate = successes_5 / len(recent)
    failures = len(recent) - successes_5
    score -= failures * 10
    if failures >= 1:
        warnings.append(f"Failed {failures} of the last {len(recent)} runs.")

    # ── Days since last success ───────────────────────────────────────────────
    days_since_success: int | None = next(
        (r["days_ago"] for r in runs if r["status"] == "success"), None
    )

    if days_since_success is None:
        score -= 40
        warnings.append("Source has never successfully returned jobs.")
    elif days_since_success > 30:
        score -= 40
        warnings.append(f"No successful scan in {days_since_success} days.")
    elif days_since_success > _BROKEN_DAYS:
        score -= 20
        warnings.append(f"No successful scan in {days_since_success} days.")
    elif days_since_success > _DEGRADING_DAYS:
        score -= 10
        warnings.append(f"Last successful scan was {days_since_success} day(s) ago.")

    # ── Zero-job runs (only penalise if historically non-zero) ───────────────
    successful_runs = [r for r in runs if r["status"] == "success"]
    avg_jobs = (
        sum(r["jobs_found"] or 0 for r in successful_runs) / len(successful_runs)
        if successful_runs else 0.0
    )
    latest_jobs = runs[0]["jobs_found"] or 0 if runs else 0

    if avg_jobs >= 2.0:
        consecutive_zeros = 0
        for r in runs:
            if r["status"] == "success" and (r["jobs_found"] or 0) == 0:
                consecutive_zeros += 1
            else:
                break
        if consecutive_zeros >= 5:
            score -= 20
            warnings.append(
                f"Returned zero jobs for {consecutive_zeros} consecutive scans "
                f"(historical avg: {avg_jobs:.1f})."
            )
        elif consecutive_zeros >= 3:
            score -= 10
            warnings.append(
                f"Returned zero jobs for {consecutive_zeros} consecutive scans "
                f"(historical avg: {avg_jobs:.1f})."
            )

    score = max(0, min(100, score))
    label = _label(score)

    return ConfidenceResult(
        score=score,
        label=label,
        warnings=warnings,
        suggested_action=_suggested_action(label),
        recent_success_rate=round(recent_success_rate, 2),
        days_since_success=days_since_success,
        latest_jobs=latest_jobs,
        avg_jobs=round(avg_jobs, 1),
    )


def update_source_confidence(source_id: str, status: str) -> ConfidenceResult:
    result = compute_confidence(source_id, status)
    note = "; ".join(result.warnings) if result.warnings else result.suggested_action
    execute(
        """
        UPDATE source_health
        SET confidence_label = ?, confidence_score = ?, confidence_note = ?
        WHERE source_id = ?
        """,
        (result.label, result.score, note, source_id),
    )
    return result
