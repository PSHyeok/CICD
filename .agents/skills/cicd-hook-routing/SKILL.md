---
name: cicd-hook-routing
description: Extend and validate repository source adapters, CI/CD eligibility policy, deduplication, and Jenkins triggers in this repository.
---

# CI/CD Hook Routing

## When to Use

- Use this skill when adding a source adapter, policy selector, or Jenkins trigger behavior.
- Use it when changing trigger safety, idempotency, or event normalization.
- Do not use it for pipeline steps inside Buildkite or Jenkins themselves.

## Required Inputs

- The inbound source payload and its stable delivery identifier.
- The normalized repository, branch, revision, event, and changed paths.
- The CI provider's authenticated trigger contract.

## Workflow

1. Implement `SourceAdapter` under `sources/` and register it in `main.py`; do not leak native
   payload shapes past the normalized event boundary.
2. Express eligibility in `policy.py` and the versioned routing manifest. Keep
   the manifest provider (file, SQLite, or HTTP) separate from inbound hooks.
3. Claim `(source, event_id, policy_id)` before the external request.
4. Keep Jenkins calls behind `TriggerClient`; read secrets only from named
   environment variables.
5. Test normalization, a positive and negative policy decision, exact outbound
   HTTP shape, and duplicate delivery behavior.

## Outputs

- Updated code under `src/cicd_router/`.
- Updated example policy and hook documentation when the contract changes.
- Passing tests under `tests/`.

## Validation

- Run `pytest`.
- Confirm repository, source branch, target branch, and optional changed-path
  filters cannot trigger a route belonging to another repository.
- Confirm a repeated event does not issue a second external request.
- Treat trigger timeouts as ambiguous; do not blindly retry them.
