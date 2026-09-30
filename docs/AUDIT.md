# Pre-submission audit

## Steward-blocker review

- Public tracked source: both contracts are committed as `.py` files.
- Concrete runner pin: both use `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`.
- Standalone mechanism: escrow, deadlines, revisions, challenges, payout accounting, withdrawals, and reputation exist beyond prompt/parse/store.
- Intermediate binding: five separate intelligent transactions bind one substantive label each before deterministic aggregation.
- Deterministic settlement: payout follows stored labels and basis-point rules.
- Deadlock prevention: every funded waiting phase has permissionless timeout closure.
- Spoof resistance: registry outcome reports require an authenticated contract sender.
- Evidence bounds: public HTTPS only, 420-character URLs, 24 KB response limit, UTF-8 decoding, and deterministic manifest SHA-256 verification.
- Failure handling: expected, external, transient, and LLM errors are separated.
- Financial consistency: locked funds are zeroed once and credited amounts sum to escrow.

## Test evidence

Direct tests cover owner authentication, spoof rejection, duplicate report idempotence, five validator replays, five separately stored dimension judgments, full acceptance, revision, partial payout, timeout refund, hard rejection, and malformed output rejection.

The GLSim test deploys both contracts, links the exact job address through the registry, and confirms stored parties and references across a five-validator simulated network. `genlayer-test` 0.29.2 does not propagate top-level transaction value in GLSim, so payable lifecycle coverage remains in direct mode and must also be confirmed in the Studio deployment record.
