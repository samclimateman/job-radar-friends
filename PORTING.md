# Porting Guide

This repo is the public, distributable friends version of Job Radar.

Mental model:

```text
career-ops        = sam-private
job-radar-friends = friend-public
```

## Default Rule

This repo is the clean room for generic product improvements. It is safe to build public UX, onboarding, packaging, source-management, source-health, and dashboard improvements here first.

Do not import private branches or commit history from `career-ops`.

## Direction of Travel

Preferred:

```text
friend-public -> sam-private
```

Build reusable features here first, then port them into `career-ops` if they are useful for Sam's private workflow.

Use extra caution:

```text
sam-private -> friend-public
```

Only accept ideas from `career-ops` after they have been reduced to generic behavior and reviewed for privacy.

## Classification

Before moving an idea between repos, classify it:

- `shared`: generic UX, dashboard layout, component behavior, source health display, onboarding concepts, backup UX, accessibility, test patterns.
- `sam-private`: sources, scoring weights, blocked phrases, personal notes, applications, resumes, cover letters, Sam-specific positioning, local paths, AI prompts tied to Sam's profile.
- `friend-public`: installer, onboarding, public docs, packaging, SQLite user-data behavior, friend-safe defaults.

This repo should only contain `shared` and `friend-public` work.

## Safe Intake From Private Repo

Prefer a written description of the idea, a small reviewed patch, or a hand-built equivalent.

Good:

```bash
git diff -- frontend/src/App.tsx frontend/src/api.ts
```

Then reimplement or adapt the generic behavior here.

Avoid:

```bash
git remote add private /path/to/career-ops
git cherry-pick <private-commit>
git push origin private-branch
```

Private commit history may contain sensitive context even when the final diff looks harmless.

## Public Safety Gate

Before pushing public changes, inspect:

```bash
git status --short
git diff --stat
git diff
git grep -n "Sam\|Samuel\|sambowers\|Defence\|MI6\|MIVD\|\.env\|DATABASE_URL\|draft_api_key"
```

Also check for:

- private source configs
- generated databases
- local cache/runtime data
- screenshots showing private notes, sources, applications, or paths
- personal materials or private prompt context

## Porting Checklist

- The change is generic or public-product-specific.
- No private branch history was pushed.
- No private paths, sources, prompts, notes, resumes, cover letters, or application records are included.
- Public tests/build pass after the port.
- If the change is backported to `career-ops`, private tests/build pass there too.

