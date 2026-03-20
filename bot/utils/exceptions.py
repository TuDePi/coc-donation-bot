class ADBConnectionError(Exception):
    """Device not found or disconnected."""


class GameStateError(Exception):
    """Stuck in unknown state, recovery failed."""


class TemplateNotFoundError(Exception):
    """Required template image missing from templates directory."""


class ConfigurationError(Exception):
    """Invalid configuration values."""
