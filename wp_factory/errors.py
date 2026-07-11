class FactoryError(RuntimeError):
    """An expected, user-actionable factory error."""


class ValidationError(FactoryError):
    """Local content or configuration is invalid."""


class WordPressError(FactoryError):
    """A WordPress request failed."""

