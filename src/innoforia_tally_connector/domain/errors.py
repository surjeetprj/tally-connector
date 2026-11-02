"""Safe, user-facing failures without remote payloads or secrets."""


class ReadError(ValueError):
    pass


class ContextMismatch(ReadError):
    pass


class Busy(ReadError):
    pass
