"""Expected identity use-case failures."""


class IdentityError(Exception):
    """Base class for safe, expected identity failures."""


class AuthenticationRequired(IdentityError):
    pass


class AccountUnavailable(IdentityError):
    pass


class InvalidOAuthFlow(IdentityError):
    pass


class OAuthProviderFailure(IdentityError):
    pass


class InvalidReturnPath(IdentityError):
    pass


class PreferenceVersionConflict(IdentityError):
    pass


class CsrfRejected(IdentityError):
    pass


class PreconditionRequired(IdentityError):
    pass


class InvalidPrecondition(IdentityError):
    pass
