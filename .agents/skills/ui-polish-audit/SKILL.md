---
name: ui-polish-audit
description: Perform a strict post-implementation visual and interaction audit of an existing web interface, then apply focused polish fixes when requested. Use for nitpicking, pixel-polish, spacing and alignment reviews, responsive fit checks, or requests to make an implemented UI feel finished. Do not use as the primary guide for inventing a product theme or for ordinary frontend feature work.
---

# UI Polish Audit

Audit the interface as a demanding design reviewer. Find small inconsistencies that ordinary implementation review misses, while preserving the product's intended visual identity.

## Boundary

This is a post-implementation quality pass. The interface, component, or flow must already exist.

- Treat the project's design system, tokens, and established patterns as the visual contract.
- Do not introduce a new aesthetic, redesign sound product decisions, or expand product functionality unless the user asks.
- Do not confuse personal taste with a defect. Change details that harm consistency, clarity, usability, accessibility, responsiveness, or perceived quality.
- Ignore architecture and business logic unless they create a visible or interactive UX problem.
- If the user requested review only, report findings without editing. If they requested fixes, apply the smallest coherent set of changes that resolves the issues.

## Audit Method

Establish the intended design language from project documentation, tokens, shared styles, and representative components before judging deviations. If a project-specific design skill was explicitly invoked, treat it as part of the contract.

Inspect the rendered interface whenever browser tooling is available. Cover the relevant routes and at least one desktop, tablet, and mobile viewport. Exercise the states that exist in scope, including hover, focus, active, disabled, loading, error, empty, selected, and content-heavy states. If rendered inspection is unavailable, continue with a source-based audit but clearly state that pixel-level verification was not completed.

Review in this order:

1. Layout integrity: overflow, clipping, collisions, unstable wrapping, misplaced overlays, and breakpoints that collapse too late.
2. Visual hierarchy: primary action clarity, heading order, density, line length, text wrapping, and competing emphasis.
3. Spatial rhythm: outer alignment, section cadence, card padding, label-to-control spacing, repeated gaps, baselines, and optical centering.
4. Component consistency: controls with the same role should share height, radius, padding, typography, icon placement, border treatment, and interaction behavior.
5. Affordance and trust: interactive elements must look interactive, static elements must not imitate controls, disabled states need an understandable reason, status information must remain visible, and links must lead somewhere meaningful.
6. Accessibility: normal text contrast of at least 4.5:1, large text contrast of at least 3:1, visible keyboard focus, semantic labels, logical focus order, reduced-motion support, and practical touch targets of at least 44 by 44 CSS pixels.
7. Content resilience: test the longest realistic labels, localization, zero and many-item states, user-provided content, and dynamic data. Do not tune a component only for the current sample string.
8. Surface polish: border weight, shadows, radii, dividers, icon alignment, background effects, and decorative motifs. These come last because they cannot repair weak structure.

Use optical judgment where mathematically equal spacing looks unequal. Preserve a recognizable spacing rhythm rather than accumulating isolated values.

## Fix and Verify

- Prefer shared tokens or shared component rules when the same issue can recur.
- Avoid broad global changes unless every affected use has been checked.
- Remove misleading decoration and interaction feedback instead of adding more visual noise.
- Reinspect every changed viewport and interaction state.
- Run the repository's relevant lint, typecheck, tests, and production build.
- Lead the handoff with the result, then summarize material corrections and any verification limitation. Do not dump the full checklist unless the user asks for an audit report.
