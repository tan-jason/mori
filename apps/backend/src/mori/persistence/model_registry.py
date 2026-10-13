"""Register every mapped table before a standalone worker flushes ORM rows."""

from importlib import import_module

_MODEL_MODULES = (
    "mori.modules.access.models",
    "mori.modules.access.usage_models",
    "mori.modules.identity.models",
    "mori.modules.learner_profiles.models",
    "mori.modules.learning.models",
    "mori.modules.sessions.models",
    "mori.modules.user.models",
)


def load_models() -> None:
    for module in _MODEL_MODULES:
        import_module(module)
