"""Custom exceptions for bot."""


class TokenError(Exception):
    """Error while loading tokens."""

    pass


class SendMessageError(Exception):
    """Error while sending message."""

    pass


class APIResponseError(Exception):
    """API return uncorrect status code."""

    pass


class ResponseTypeError(Exception):
    """Wrong type in API response."""

    pass


class StatusCodeError(Exception):
    """Wrong status code in API response."""

    pass


class KeyError(Exception):
    """Wrong key in API response."""

    pass


class RequestError(Exception):
    """Can't do request to API."""

    pass


class ResponseError(Exception):
    """API refuse to service."""

    pass


class HomeworkStatusError(Exception):
    """Unexpected homework status in API response."""

    pass
