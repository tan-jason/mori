---
name: mori-frontend-design
description: Build or modify the Mori language-learning web frontend while preserving its established visual language and consumer UX standards. Use for frontend features, components, pages, states, or styling changes in the Mori lang-learner project. Do not use as a substitute for a dedicated post-implementation pixel-polish audit.
---

# Mori Frontend Design

Keep every Mori frontend change recognizably part of the same calm, tactile conversation studio.

Before making a visual change, read [references/design-contract.md](references/design-contract.md). Then inspect the nearest existing component, shared styles, and relevant product requirements. The reference defines the stable direction; the current repository is authoritative for intentionally evolved implementation details.

## Scope

Use this skill while creating or changing Mori frontend UI. It governs the design decisions made during implementation:

- Extend existing tokens and patterns before creating near-duplicates.
- Preserve the current product behavior and data boundaries unless the request includes a behavior change.
- Design the full component contract from the start: default, hover, focus, active, disabled, loading, error, empty, and responsive states that are relevant.
- Keep content and layout resilient across all supported target languages. Never hardcode Mandarin-specific presentation when the active language profile supplies the value.
- Do not expose engineering terms such as scaffold, backend mutation, realtime agent, or implementation status in consumer-facing copy.
- Do not introduce a UI framework, icon family, font, or new visual motif unless it improves the whole system and the user requested or approved the direction.

## Working Approach

1. Identify the user goal, route, component role, and existing pattern it should extend.
2. Read the design contract and the smallest relevant set of source files.
3. Implement with shared variables, semantic markup, accessible interactions, and responsive behavior. Prefer a reusable correction when a pattern will recur.
4. Inspect the rendered result at appropriate desktop, tablet, and mobile widths when browser tooling is available. Check realistic long copy and all implemented states.
5. Run the relevant lint, typecheck, tests, and production build.

When guidance conflicts, follow this order: explicit user direction, product requirements, the design contract, then nearby precedent. A nearby inconsistency is not a pattern worth copying.

This skill keeps work on-theme during construction. Use `ui-polish-audit` separately when the user asks for a deliberately unforgiving final design pass.
