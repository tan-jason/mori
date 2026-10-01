"""Expected session entry-point failures."""


class InvalidIdempotencyKey(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


class VoiceEntitlementUnavailable(Exception):
    pass


class VoiceSessionLimitReached(Exception):
    def __init__(self, max_sessions: int, reset_period: str | None) -> None:
        self.max_sessions = max_sessions
        self.reset_period = reset_period
        super().__init__(f"voice session limit reached: {max_sessions}")


class SessionNotFound(Exception):
    pass


class PlanUnavailable(Exception):
    pass


class InvalidSessionSetup(Exception):
    pass


class SessionNotConnectable(Exception):
    pass


class VoiceNotConfigured(Exception):
    pass


class VoiceProviderUnavailable(Exception):
    pass


class VoiceRetryLimitReached(Exception):
    pass
