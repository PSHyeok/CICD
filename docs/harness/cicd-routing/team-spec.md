# CI/CD Routing Team Specification

## Architecture

The workflow is a sequential Pipeline:

```text
source adapter -> normalized event -> manifest load -> route match -> atomic claim -> Jenkins
```

One implementation owner is the default. New repository systems are isolated
behind `SourceAdapter`; policy, idempotency, and Jenkins triggering remain
unchanged. A separate reviewer is useful for authentication or concurrency changes.

## Contracts

| Stage | Input | Output | Failure behavior |
| --- | --- | --- | --- |
| Normalize | validated source hook | `NormalizedEvent` | reject invalid input |
| Manifest load | file, SQLite, or HTTP source | versioned routes | fail before triggering |
| Match | event and manifest routes | all ordered matching routes | return no matches |
| Claim | source, event ID, policy ID | unique durable claim | return duplicate |
| Trigger | event and Jenkins config | queue URL | persist failure; no blind retry |

The normalized model is the source of truth between inbound adapters and
policy. `TriggerClient` is the source of truth between routing and Jenkins.

## Ownership and permissions

- The implementation owner writes `src/`, `tests/`, config examples, and API docs.
- Runtime reads the routing manifest and secret environment variables, writes the SQLite
  database, and makes network calls only to configured CI endpoints.
- Parallel writes are advisory only and should be serialized unless isolated
  workspaces and non-overlapping files are available.

## Acceptance

- Normal, non-matching, excluded-path, duplicate, and provider-failure flows are
  explicit.
- Secrets do not appear in policy or logs.
- Tests cover repository/branch/path isolation and exact provider endpoint shape.
- Partial provider failure remains visible in the response and trigger ledger.

## Safe degradation

- If a provider or credential is unavailable, other matching policies continue
  and the failed result is preserved.
- If the durable store is unavailable, fail the request before triggering CI.
- If a trigger response is ambiguous, keep the claim and require operator
  reconciliation rather than risking a duplicate build.
