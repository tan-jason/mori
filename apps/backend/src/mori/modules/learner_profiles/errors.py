"""Profile and onboarding failures."""


class LearnerProfileError(Exception):
    """Base class for expected profile failures."""


class PreconditionRequired(LearnerProfileError):
    pass


class InvalidPrecondition(LearnerProfileError):
    pass


class PreferenceVersionConflict(LearnerProfileError):
    pass


class UnsupportedLanguagePair(LearnerProfileError):
    pass


class OnboardingRequired(LearnerProfileError):
    pass


class OnboardingIdempotencyConflict(LearnerProfileError):
    pass


class ProfileAlreadyConfirmed(LearnerProfileError):
    pass


class InvalidOnboardingKey(LearnerProfileError):
    pass
