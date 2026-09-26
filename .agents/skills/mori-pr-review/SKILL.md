---
name: mori-pr-review
description: Review a Mori pull request for correctness, robustness, risk, and mergeability. Use when asked to review a PR or decide whether it is safe to merge; do not use for ordinary implementation or a visual polish audit.
---

# Mori PR Review

Give an independent, evidence-based merge recommendation. Review the change as shipped in this PR, including its migrations and API contracts. Do not edit code or post a GitHub review unless the user asks.

## Establish the review target

- Identify the PR's base and head commits, scope, and stated verification. Confirm the local checkout matches the head before relying on it. Review the base-to-head diff and the surrounding code needed to follow changed behavior.
- Read the relevant product and architecture contracts in `docs/PRD.md` and `docs/architecture/` when they affect the change. Treat the implementation and current PR scope as evidence too; do not turn an unimplemented future milestone into a blocker for a deliberately limited slice.
- For backend changes, trace the request through authentication, authorization, application logic, transaction boundaries, database constraints, migrations, error mapping, and tests. Pay particular attention to session lifecycle, entitlement accounting, idempotency, concurrency, expiry, and recovery when those areas change.
- For web changes, trace the user action through gateway calls and state handling. Check relevant accessibility, responsive behavior, and the API contract. Use rendered inspection when visual behavior is material.

## Verify material claims

- Look for a concrete failure path, including the inputs and state needed to trigger it. Check whether existing guards, constraints, or later transitions already prevent it.
- Run focused checks that can resolve a real uncertainty. Backend commands are in `apps/backend/README.md`; web scripts are in `apps/web/package.json`. Report what ran and what could not run. Passing tests do not replace inspection of uncovered behavior.
- Separate current defects from follow-up work. A future integration dependency blocks this PR only if this PR makes an unsafe or unusable state possible within its stated scope.

## Report the decision

Lead with **Mergeable** or **Not mergeable**. For each blocking finding, give a severity, a precise file and line reference, the failure scenario, the consequence if merged, and the change needed to resolve it. Include only findings supported by the code. Group related symptoms under one root cause.

Mention material nonblocking risks or verification limits briefly. If no blockers remain, say so plainly and give the key evidence behind the recommendation. Do not present a hypothetical concern as a defect.
