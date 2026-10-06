# Beginner lessons 1 and 2: tutor guidance draft

**Status:** Draft for product and transcript review. These shared blocks are not published in the lesson profile or used by the session service yet.

These are language-independent lesson blocks for the Realtime tutor. The same lesson profile applies to every supported language pair, while progress remains separate for each learner language profile. At runtime, the compiler includes exactly one block with the shared tutor policy, the Beginner level policy, the selected language-pair policy, and bounded learner context. Shared policy owns Mori's tone, speaking speed, proactive follow-ups and topic pivots, correction preference, and the balance of base-language explanation with target-language practice. The lesson block adds a conversational capability and guidance for creating opportunities to use it. Neither block is an ordered question template.

The blocks use **base language** and **target language** so the selected learner profile controls the languages. The shared lesson profile stores only the meaning of a helpful phrase, such as asking what something means. Its actual target-language wording and pronunciation support come from the selected pair course. Helpful phrases are available for teaching, not required pass phrases.

Either helpful phrase may be taught in either lesson when the learner needs it; the table shows where it is most likely to be introduced.

| Field | Lesson 1 | Lesson 2 |
| --- | --- | --- |
| Draft key | `beginner-01-life-context` | `beginner-02-interests-and-follow-ups` |
| Learner title | Talk about your life | Keep a conversation about your life going |
| Capability | Say where you live in broad terms and describe work, study, or another basic part of daily life. | Describe an interest or familiar activity, add a related detail, respond to a follow-up, and contribute something that keeps the exchange going. |
| Prerequisite | Beginner placement. Basic name and origin can be scaffolded if needed. | Lesson 1 demonstrated, or supported placement evidence for the same capability. |
| Helpful phrase | A natural way to say "I am learning [target language]." | A natural way to ask "What does that mean?" |

## Tutor block: lesson 1

```text
# Current Lesson: Beginner 1 - Talk about your life

Aim: Help the learner say a little more about their life than their name and origin. By the end of this conversation, give them chances to describe two aspects they choose, such as where they live in broad terms, what they do during the day, or whether they work, study, or do something else.

Guide the conversation:
- Treat a basic name-and-origin introduction as familiar. If it is not familiar to this learner, briefly help them form it and continue into the lesson.
- Explore one simple aspect of their life, then follow their answer toward another. Ask connected follow-ups rather than working through a list of personal questions.
- If it fits, teach a way to say "I am learning [target language]" and invite the learner to adapt it. This phrase is optional.
- Broad or imagined descriptions count. Do not press for a specific personal detail.

Create opportunities for the learner to express two distinct aspects in their own words and respond to a natural follow-up about one of them. If they needed a complete model, offer another opportunity later with a different detail.
```

## Tutor block: lesson 2

```text
# Current Lesson: Beginner 2 - Keep a conversation about your life going

Aim: Build on basic life descriptions. Help the learner talk about an interest or familiar activity, add a connected detail, handle a related follow-up, and contribute a simple question or extra thought that keeps the exchange moving.

Guide the conversation:
- Begin with an interest or activity the learner chooses. A current, permitted context hook may suggest one; confirm it rather than assuming an old detail is still true. An imagined activity also works.
- Invite a small related detail, then choose a follow-up that fits the answer. After a few connected turns, leave room for the learner to ask a simple question back or add another thought.
- Reuse useful language from lesson 1 where it fits. If the learner is confused, teach a way to ask "What does that mean?" in the target language, answer it, and continue. This phrase is optional.

Create opportunities for the learner to describe an interest or activity, add a related detail, answer an unannounced follow-up, and contribute to the next turn. If they needed a complete model, return to the capability through a different example.
```

## Post-session evidence criteria

The worker evaluates the pinned lesson from finalized learner and tutor turns. The tutor prompt creates opportunities; it does not grade. These draft criteria require transcript review before evidence rules are enabled.

| Lesson | Evidence for `demonstrated` | `needs_practice` | `insufficient_evidence` |
| --- | --- | --- | --- |
| 1 | Across at least two distinct learner turns, the learner independently communicates two different basic life aspects, and responds meaningfully to a related follow-up. Broad or fictional details count. A short scaffold earlier in the session does not disqualify later independent use. | The learner participates but still needs a complete modeled answer for the life details or follow-up, or cannot yet communicate them in the target language. | The conversation ends too early, usable learner turns are missing, or the tutor never offers enough opportunities to assess the capability. |
| 2 | Across connected turns, the learner independently describes an interest or familiar activity, adds a related detail, answers a relevant follow-up, and asks a simple related question or volunteers a further relevant thought. Exact wording and topic do not matter. | The learner participates but can only repeat a complete model, gives no connected detail after support, or cannot respond to a follow-up yet. | The conversation ends too early, usable learner turns are missing, or the tutor never offers enough opportunities to assess the capability. |

"Independent" means the learner chooses and produces the meaning, even if they reuse language learned earlier. Immediately repeating a full tutor-supplied answer is practice rather than passage evidence. The worker cites exact learner turns and checks the preceding tutor turns for modeling. Helpful learning phrases are optional supports and do not determine passage. Transcript evidence does not establish pronunciation mastery.

## Runtime context contract for these drafts

The compiler selects the block by the shared lesson key and lesson-profile version pinned in the session plan. The planner uses the learner's language profile, compatible pair course, and last committed learning snapshot to select that key. The separate context block can include `first`, `continuation`, or `review`, bounded validated strengths and repair needs, and currently eligible memory hooks. A continuation means the learner has had a usable encounter with the lesson; it does not assert they failed. Pending analysis cannot advance the lesson. The tutor uses a repair need to choose a different opportunity, without repeating a prior conversation or claiming a permanent weakness.

## Transcript review cases

- First encounter with a learner who can introduce themselves but needs an explanation in their selected base language for a new target-language phrase.
- First encounter with an "I'm not sure" learner who needs help with name and origin before continuing.
- Continuation with a supported difficulty, using a different follow-up rather than replaying the prior exchange.
- Learner declines a personal question and uses a broad or imagined example.
- Learner asks for an unrelated topic; Mori follows it where possible while preserving the lesson capability.
- Tutor provides a complete model and the learner repeats it, followed by a later independent attempt.
