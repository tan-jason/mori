# Mori Frontend Design Contract

## Product Character

Mori is a calm, adult conversation studio for language learners. The interface should feel patient, warm, tactile, and quietly confident. It borrows from study notebooks, index cards, paper, and handwritten annotations without becoming childish or decorative for its own sake.

Avoid generic SaaS dashboard styling, competitive gamification, streak pressure, neon color, excessive gradients, glass everywhere, dense admin layouts, and guilt-based engagement. Product copy should be supportive, plain, and nonjudgmental.

## Visual Foundation

Treat the variables in `apps/web/src/styles/global.css` as the implementation source of truth. The established palette is:

- Paper background: warm cream, currently `#f4f0e5`.
- Raised surface: soft ivory, currently `#fffdf6`.
- Primary ink: deep green-black, currently `#20312c`.
- Secondary text: muted green-gray, currently `#626d67`.
- Primary brand action: forest green, currently `#4e7568`, with a darker `#426f62` variant.
- Quiet green surface: currently `#eef4ef`.
- Warm accent: persimmon, currently `#d9714b`; use its darker ink variant for small text.
- Supporting blue ink: currently `#355e70`.
- Borders: warm gray rather than cold neutral gray.

Use color semantically. Forest communicates action, progress, and active state. Persimmon is a restrained annotation or emphasis color. Do not let accent color compete with the primary action.

The body type is a legible humanist system sans. The display face is handwriting-inspired and belongs on the brand, major headings, learning terms, and a small number of expressive metrics. Do not use the display face for long body copy, form controls, or dense metadata.

Normal supporting copy must remain readable against paper and ivory. Do not reduce important labels below 11 CSS pixels. Maintain at least 4.5:1 contrast for normal text and 3:1 for large text.

## Shape, Depth, and Decoration

The current radius family is approximately 30px for major containers, 22px for cards, and 14px for controls and compact surfaces. Match the role before matching a literal number.

Shadows should suggest stacked paper, not floating glass. Keep them soft and low-opacity. Stronger physical shadows belong mainly to primary actions or intentional paper artifacts.

Notebook rules, tape, book shapes, paper grain, and rotated cards are signature motifs. Use them at focal moments such as the lesson board or a tutor note. Most functional cards should remain quiet. Repeating the motif on every surface makes the experience noisy and weakens hierarchy.

## Layout and Rhythm

- Align page content to the shared shell rather than inventing route-specific widths.
- Preserve the established spacing rhythm based primarily on 4, 8, 12, 16, 20, 24, 32, 48, and 64 CSS pixels.
- Major sections need more separation than related items within a section.
- Controls of the same role should share height, internal padding, chevron placement, radius, label spacing, and helper-text spacing.
- Use optical alignment for text, icons, badges, and asymmetric shapes.
- Collapse multi-column content before either column becomes cramped. Do not wait for actual overflow.
- Mobile gutters must remain comfortable at 320px. Essential statuses and actions cannot disappear merely to make a row fit.

The existing shell targets roughly 1180px for page content and a slightly wider header. Treat those as system constraints unless a feature has a clear reading-width reason to be narrower.

## Components and Interaction

Controls should generally provide at least a 44px touch target, with primary form controls around 48 to 50px high. Maintain a visible persimmon-toned focus treatment.

Primary buttons use forest, light text, and restrained physical depth. Secondary actions are quieter ivory or green-tinted surfaces. Destructive actions use muted warm red and should never be visually stronger than the primary task until confirmation is required.

Only interactive cards and rows receive hover elevation or movement. Static information cards must not behave visually like links. Every visible link must lead to a meaningful destination. Disabled controls should look unavailable and have an understandable visible context; do not rely only on a `title` attribute.

Forms need consistent label-to-control and control-to-helper spacing. Save actions should distinguish unchanged, dirty, saving, saved, and error states when those states exist. Do not imply persistence that the implementation does not provide.

Use semantic HTML first. Preserve visible keyboard focus, logical heading order, accessible names, reduced-motion behavior, and screen-reader access to meaningful learning content.

## Content and Language Resilience

Mori speaks with patience and respect. Prefer clear statements over cute system copy. Encourage practice without guilt, judgment, emotional dependency, or false human claims.

The app supports multiple target languages. Components must accommodate long Latin-script terms, diacritics, non-Latin characters, pronunciation strings, and language marks. Use `LanguageProfileProvider` data rather than embedding one language in shared UI.

Internal implementation limitations should become honest consumer language such as "not available in this preview" or "coming soon." Do not surface stack names, API state, backend terminology, or developer placeholders.

## Relationship to UI Polish

This contract guides creation and modification. It is not the final inspection procedure. After a substantial frontend change, use the separate `ui-polish-audit` skill when a strict spacing, fit, hierarchy, and interaction review is requested.
