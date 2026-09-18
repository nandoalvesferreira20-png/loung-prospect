"""Only these provider errors contain messages safe to show to the operator."""


class SalesConfigurationError(ValueError):
    pass


class SalesProviderError(RuntimeError):
    pass
