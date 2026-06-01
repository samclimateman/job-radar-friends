"""Tests for source confidence scoring logic.

Mocks the DB execute call so tests run without a real database and cover
the scoring branches directly. Mirrors career-ops confidence.py test logic.
"""

import pytest

from job_radar.ingestion.confidence import ConfidenceResult, compute_confidence


def _run(*, status="success", jobs_found=5, error=None, days_ago=0):
    return {"status": status, "jobs_found": jobs_found, "error": error, "days_ago": days_ago}


def _patch(monkeypatch, rows):
    monkeypatch.setattr(
        "job_radar.ingestion.confidence.execute",
        lambda *a: rows,
    )


# ── No history ────────────────────────────────────────────────────────────────

def test_no_history_returns_unknown(monkeypatch):
    _patch(monkeypatch, [])
    result = compute_confidence("src-1", "active")
    assert result.label == "unknown"
    assert result.score == 0


# ── Disabled / needs_review bypass ───────────────────────────────────────────

def test_disabled_source_bypasses_db(monkeypatch):
    called = []
    monkeypatch.setattr("job_radar.ingestion.confidence.execute", lambda *a: called.append(a) or [])
    result = compute_confidence("src-1", "disabled")
    assert called == []   # no DB query
    assert result.label == "unknown"


def test_needs_review_bypasses_db(monkeypatch):
    called = []
    monkeypatch.setattr("job_radar.ingestion.confidence.execute", lambda *a: called.append(a) or [])
    result = compute_confidence("src-1", "needs_review")
    assert called == []
    assert result.label == "manual"


# ── Healthy ───────────────────────────────────────────────────────────────────

def test_perfect_history_is_healthy(monkeypatch):
    rows = [_run(days_ago=0)] * 10
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.label == "healthy"
    assert result.score == 100
    assert result.warnings == []
    assert result.recent_success_rate == 1.0


def test_one_old_failure_still_healthy(monkeypatch):
    # 4 recent successes, 1 failure — score drops 10 but stays healthy
    rows = [_run(days_ago=0)] * 4 + [_run(status="failed", days_ago=5)]
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 90
    assert result.label == "healthy"
    assert len(result.warnings) == 1


# ── Watch ─────────────────────────────────────────────────────────────────────

def test_two_recent_failures_is_watch(monkeypatch):
    rows = [_run(days_ago=0)] * 3 + [_run(status="failed", days_ago=1)] * 2
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 80
    assert result.label == "healthy"  # 80 = healthy band; 2 failures = -20


def test_stale_7_days_is_watch(monkeypatch):
    # Last success was 8 days ago → -10
    rows = [_run(days_ago=8)] + [_run(days_ago=9)] * 4
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 90
    assert result.label == "healthy"
    assert any("8 day" in w for w in result.warnings)


# ── Degrading ─────────────────────────────────────────────────────────────────

def test_three_recent_failures_is_degrading(monkeypatch):
    rows = [_run(days_ago=0)] * 2 + [_run(status="failed", days_ago=1)] * 3
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 70
    assert result.label == "watch"


def test_stale_15_days_is_degrading(monkeypatch):
    rows = [_run(days_ago=15)] * 5
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 80   # -20 for >14d
    assert result.label == "healthy"


def test_three_consecutive_zeros_penalised(monkeypatch):
    # avg_jobs >= 2 historically, but last 3 successful runs returned 0
    rows = (
        [_run(jobs_found=0, days_ago=0)] * 3
        + [_run(jobs_found=5, days_ago=4)] * 7
    )
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 90   # -10 for 3 consecutive zeros
    assert any("consecutive" in w for w in result.warnings)


def test_five_consecutive_zeros_bigger_penalty(monkeypatch):
    rows = (
        [_run(jobs_found=0, days_ago=0)] * 5
        + [_run(jobs_found=5, days_ago=6)] * 5
    )
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 80   # -20 for 5+ consecutive zeros
    assert any("consecutive" in w for w in result.warnings)


# ── Broken ────────────────────────────────────────────────────────────────────

def test_five_consecutive_failures_is_broken(monkeypatch):
    rows = [_run(status="failed", error="timeout", days_ago=i) for i in range(5)]
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score <= 39
    assert result.label == "broken"


def test_never_succeeded_is_broken(monkeypatch):
    rows = [_run(status="failed", days_ago=i) for i in range(3)]
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.label in ("broken", "degrading")
    assert any("never" in w.lower() for w in result.warnings)


def test_stale_31_days_is_broken(monkeypatch):
    rows = [_run(days_ago=31)] * 5
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert result.score == 60   # -40 for >30d
    assert result.label == "watch"


# ── Fields ────────────────────────────────────────────────────────────────────

def test_result_fields_are_populated(monkeypatch):
    rows = [_run(jobs_found=3, days_ago=1)] * 5
    _patch(monkeypatch, rows)
    result = compute_confidence("src-1", "active")
    assert isinstance(result, ConfidenceResult)
    assert result.latest_jobs == 3
    assert result.avg_jobs == 3.0
    assert result.days_since_success == 1
    assert result.recent_success_rate == 1.0
    assert result.suggested_action != ""
