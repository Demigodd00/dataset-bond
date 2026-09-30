# Architecture

## Linked contracts

```text
registry owner ──registers exact address──▶ DatasetBondRegistry
                                                ▲
                                                │ authenticated final report
                                                │
buyer ──funds──▶ DatasetBondJob ◀──delivers── provider
                     │
                     ├─ fetch manifest, validation evidence, provenance
                     ├─ bind five validator-replayed labels
                     ├─ revision or scoped challenge
                     └─ deterministic payout → pull-payment credits
```

The registry never holds escrow funds. Each job is financially isolated and can report only its own final result. Registration is owner-authenticated so arbitrary accounts cannot manufacture reputation.

## Job state machine

```text
AWAITING_FUNDING
  └─ fund ─▶ FUNDED
       ├─ decline/cancel/timeout ─▶ SETTLED
       └─ accept ─▶ IN_PROGRESS
            ├─ delivery timeout ─▶ SETTLED
            └─ submit ─▶ SUBMITTED
                 ├─ assessment timeout ─▶ SETTLED
                 └─ assess ─▶ REVISION_REQUIRED ─▶ SUBMITTED
                              or REVIEW_WINDOW
                                   ├─ challenge ─▶ CHALLENGED ─▶ REVIEW_WINDOW
                                   ├─ buyer accept ─▶ SETTLED
                                   └─ deadline finalize ─▶ SETTLED
```

Every funded waiting state has a permissionless closure path. No cooperation from an absent buyer, provider, or assessor is needed to unlock funds.

## Consensus boundary

The nondeterministic operation includes all three HTTPS fetches and the LLM assessment. Validators repeat the fetches and prompt independently. Consensus compares the five payment-relevant labels exactly; the summary is explanatory and does not affect settlement.

Fetched content is bounded to 24 KB per document, must decode as UTF-8, and is explicitly marked as untrusted data in the prompt. The contract distinguishes expected user errors, stable external-source errors, retryable transient failures, and malformed LLM output.

## Financial accounting

Settlement zeros locked escrow before crediting recipients. Provider and buyer credits sum exactly to the original escrow, including integer rounding. Withdrawals zero credit before emitting a transfer. The registry receives only basis-point results, not funds.

