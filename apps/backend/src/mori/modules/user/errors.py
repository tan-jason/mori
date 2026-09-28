"""Account access failures."""


class AccountError(Exception):
    """Base class for expected account failures."""


class AccountUnavailable(AccountError):
    pass
