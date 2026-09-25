"""Expected session entry-point failures."""


class InvalidIdempotencyKey(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


class VoiceEntitlementUnavailable(Exception):
    pass


class SessionNotFound(Exception):
    pass
