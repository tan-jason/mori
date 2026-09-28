"""Authentication failures."""


class IdentityError(Exception):
    """Base class for safe, expected identity failures."""


class AuthenticationRequired(IdentityError):
    pass


class InvalidOAuthFlow(IdentityError):
    pass


class OAuthProviderFailure(IdentityError):
    pass


class InvalidReturnPath(IdentityError):
    pass


class CsrfRejected(IdentityError):
    pass
