"""Opt-in Realtime regression check using synthetic learner context.

Uses the configured model and API key. Makes provider requests, without creating
application sessions or consuming learner grants. Reviews generated text/transcripts,
without evaluating acoustic quality, microphone input, or browser delivery.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from openai import AsyncOpenAI
from openai.resources.realtime.realtime import AsyncRealtimeConnection

from mori.config import Settings
from mori.modules.curriculum.catalog import CodeCourseCatalog
from mori.modules.curriculum.curriculum import FRAMEWORK_ID, LESSONS
from mori.modules.sessions.prompt import (
    BASE_POLICY_VERSION,
    PromptObjective,
    PromptPlan,
    PromptProfile,
    compile_realtime_config,
)

_NAME_REQUEST = re.compile(
    r"\b(?:what(?:'s| is)|tell me|say|share|give|choose|use|add|try)\b"
    r"[^.!?\n]{0,100}\b(?:your|preferred) name\b|"
    r"你(?:叫什么|的名字)|名字(?:是什么|叫)|怎么称呼",
    re.IGNORECASE,
)
_OPENING_TEACHING = re.compile(
    r"\b(?:new|useful|helpful) phrase\b|\b(?:it|this|which) means\b|"
    r"\btry (?:saying|this phrase)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Scenario:
    name: str
    context: tuple[tuple[str, str], ...]
    learner_reply: str


SCENARIOS = (
    Scenario(
        "returning_introduction",
        (
            (
                "learning",
                'Introduced himself as "Jason" using 我叫, 我住在, and 我是 + occupation.',
            ),
            ("learning", "Practiced 我喜欢 + activity and 你喜欢做什么? to talk about interests."),
            ("learning", "Used 通常, 下班后 and 周末 to describe familiar routines."),
            ("insight", "Enjoys playing beach volleyball."),
        ),
        "我在一家小公司工作。",
    ),
    Scenario(
        "returning_interest",
        (
            ("learning", "Practiced 我喜欢 + activity to say what they enjoy."),
            ("insight", "Enjoys playing beach volleyball."),
        ),
        "我周末喜欢打沙滩排球。",
    ),
    Scenario("first_beginner", (), "I don't understand that phrase. Can you help?"),
)


async def _tutor_response(connection: AsyncRealtimeConnection) -> str:
    await connection.response.create()
    parts: list[str] = []
    async for event in connection:
        if event.type == "error":
            raise RuntimeError(f"Realtime error: {event.error.code}")
        if event.type in {"response.output_text.delta", "response.output_audio_transcript.delta"}:
            parts.append(event.delta)
        if event.type == "response.done":
            if event.response.status != "completed":
                raise RuntimeError(f"Incomplete response: {event.response.status}")
            result = "".join(parts).strip()
            if not result:
                raise RuntimeError("Empty tutor response")
            return result
    raise RuntimeError("Realtime connection ended before the response")


async def evaluate(
    scenario: Scenario, settings: Settings, client: AsyncOpenAI, modality: str
) -> dict[str, object]:
    course = CodeCourseCatalog().course_version(
        base_language_id="english", target_language_id="mandarin", version=FRAMEWORK_ID
    )
    assert course is not None
    lesson = LESSONS[0]
    plan = PromptPlan(
        "learning_plan_v1",
        "learning",
        "beginner",
        FRAMEWORK_ID,
        BASE_POLICY_VERSION,
        course.language_policy_version,
        "beginner",
        None,
        (),
        (PromptObjective("graded", lesson.label, lesson.key),),
    )
    profile = PromptProfile(
        "english",
        "mandarin",
        "balanced",
        "gentle",
        "Talk with family",
        "Casual conversations with relatives",
        "",
        scenario.context,
    )
    compiled = compile_realtime_config(plan=plan, profile=profile, course=course)
    async with (
        asyncio.timeout(45),
        client.realtime.connect(
            model=settings.openai_realtime_model,
            max_retries=0,
        ) as connection,
    ):
        await connection.session.update(
            session={
                "type": "realtime",
                "instructions": compiled.instructions,
                "output_modalities": [modality],
                "audio": {
                    "output": {
                        "voice": settings.openai_realtime_voice,
                        "speed": compiled.output_speed,
                    },
                },
            }
        )
        async for event in connection:
            if event.type == "error":
                raise RuntimeError(f"Realtime error: {event.error.code}")
            if event.type == "session.updated":
                instructions = event.session.instructions or ""
                if sha256(instructions.encode()).hexdigest() != compiled.instructions_sha256:
                    raise RuntimeError("Provider acknowledged different instructions")
                break
        opening = await _tutor_response(connection)
        await connection.conversation.item.create(
            item={
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": scenario.learner_reply}],
            }
        )
        follow_up = await _tutor_response(connection)
    failures: list[str] = []
    if _NAME_REQUEST.search(opening) or _NAME_REQUEST.search(follow_up):
        failures.append("asks_for_name")
    if scenario.context and ("我叫" in opening or "我叫" in follow_up):
        failures.append("restarts_practised_introduction")
    if _OPENING_TEACHING.search(opening):
        failures.append("teaches_before_first_attempt")
    return {
        "scenario": scenario.name,
        "policy": compiled.base_policy_version,
        "instructions_sha256": compiled.instructions_sha256,
        "opening": opening,
        "learner_reply": scenario.learner_reply,
        "follow_up": follow_up,
        "failures": failures,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--modality", choices=("text", "audio"), default="text")
    parser.add_argument("--scenario", choices=[scenario.name for scenario in SCENARIOS])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    if settings.openai_api_key is None:
        raise SystemExit("OPENAI_API_KEY is required for this opt-in provider evaluation.")
    results: list[dict[str, object]] = []
    async with AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()) as client:
        for trial in range(1, args.trials + 1):
            for scenario in SCENARIOS:
                if args.scenario and scenario.name != args.scenario:
                    continue
                try:
                    result = await evaluate(scenario, settings, client, args.modality)
                except Exception as error:
                    result = {
                        "scenario": scenario.name,
                        "failures": ["evaluation_error"],
                        "error_type": type(error).__name__,
                    }
                result["trial"] = trial
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if result.get("error_type"):
                    break
            if results[-1].get("error_type"):
                break
    report = {
        "model": settings.openai_realtime_model,
        "created_at": datetime.now(UTC).isoformat(),
        "modality": args.modality,
        "results": results,
        "limitations": (
            "Heuristic name/restart checks plus manual transcript review; "
            "no acoustic, microphone, or browser-delivery evaluation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if any(result["failures"] for result in results):
        raise SystemExit("Tutor opening regression detected; inspect the report.")


if __name__ == "__main__":
    asyncio.run(main())
