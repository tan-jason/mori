"""Expected session entry-point failures."""


class InvalidIdempotencyKey(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


class VoiceEntitlementUnavailable(Exception):
    pass


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
