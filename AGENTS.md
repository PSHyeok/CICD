# Repository Agents Guide

## What

- This service receives GitHub, Perforce, and repo-manifest hooks, evaluates declarative policy, and triggers Jenkins.
- Application code lives in `src/cicd_router/`; routing policy lives outside code as YAML.
- `SourceAdapter` and the normalized event model isolate repository-specific payloads from policy and Jenkins triggering.

## Why

- Source and CI integrations must remain replaceable; do not put provider payload details into policy evaluation.
- Trigger claims are persisted before external calls to avoid accidental duplicate builds.

## How

- Install: `python3 -m pip install -e '.[dev]'`
- Test: `pytest`
- Run: `CICD_ROUTER_CONFIG=config/policies.example.yaml uvicorn cicd_router.main:app --reload`
- Reusable workflow guidance: `.agents/skills/cicd-hook-routing/SKILL.md`
- Architecture and failure policy: `docs/harness/cicd-routing/team-spec.md`
