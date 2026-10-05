"""Server-side OpenAI Realtime SDP exchange. Browser media never passes through Mori."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from urllib.parse import quote, urlsplit

import httpx2


class DefinitiveProviderFailure(Exception):
    """The provider rejected the request before creating a usable call."""


class AmbiguousProviderFailure(Exception):
    """A call may exist, so automatic duplicate creation is unsafe."""

    def __init__(self, *, call_id: str | None = None) -> None:
        super().__init__("provider call creation outcome is uncertain")
        self.call_id = call_id


@dataclass(frozen=True, slots=True)
class CreatedCall:
    call_id: str
    answer_sdp: str


class OpenAIRealtimeProvider:
    def __init__(self, *, api_key: str, base_url: str = "https://api.openai.com") -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def create_call(
        self,
        *,
        offer_sdp: str,
        instructions: str,
        speed: float,
        model: str,
        voice: str,
        safety_identifier: str,
        client_request_id: str,
    ) -> CreatedCall:
        if not isfinite(speed) or not 0.25 <= speed <= 1.5:
            raise ValueError("Realtime output speed must be between 0.25 and 1.5")
        session = {
            "type": "realtime",
            "model": model,
            "instructions": instructions,
            "audio": {
                "input": {
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                },
                "output": {"voice": voice, "speed": speed},
            },
        }
        try:
            async with httpx2.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self._base_url}/v1/realtime/calls",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "OpenAI-Safety-Identifier": safety_identifier,
                        "X-Client-Request-Id": client_request_id,
                    },
                    files={
                        "sdp": (None, offer_sdp),
                        "session": (None, json.dumps(session, separators=(",", ":"))),
                    },
                )
        except httpx2.RequestError as error:
            raise AmbiguousProviderFailure from error
        if 400 <= response.status_code < 500 and response.status_code != 408:
            raise DefinitiveProviderFailure
        if response.status_code != 201:
            raise AmbiguousProviderFailure
        location = response.headers.get("Location", "")
        path = urlsplit(location).path
        prefix = "/v1/realtime/calls/"
        call_id = path.removeprefix(prefix) if path.startswith(prefix) else ""
        if not call_id or "/" in call_id:
            raise AmbiguousProviderFailure
        if not response.text.strip():
            raise AmbiguousProviderFailure(call_id=call_id)
        return CreatedCall(call_id=call_id, answer_sdp=response.text)

    async def hangup(self, call_id: str) -> None:
        try:
            async with httpx2.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._base_url}/v1/realtime/calls/{quote(call_id, safe='')}/hangup",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx2.RequestError as error:
            raise AmbiguousProviderFailure from error
        if response.status_code not in {200, 204, 404}:
            raise AmbiguousProviderFailure
