
import requests

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlsplit


REQUEST_TIMEOUT = 60

SAFE_HTTP_MESSAGES = {
    400: "The request contains invalid information.",
    401: "Authentication failed. Please check your credentials.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    409: "This operation conflicts with existing information.",
    422: "Some submitted information is invalid.",
    429: "Too many requests. Please try again later.",
}

PUBLIC_AUTH_ENDPOINTS = {
    "/auth/login",
    "/auth/register",
}


@dataclass
class APIResult:
    data: Optional[Any] = None
    error: Optional[str] = None
    unauthorized: bool = False


def _validate_base_url(api_base_url):
    """Validate the configured API base URL."""

    if not isinstance(api_base_url, str) or not api_base_url.strip():
        return None

    try:
        parsed = urlsplit(api_base_url.strip())

        if parsed.scheme.lower() not in {"http", "https"}:
            return None

        if not parsed.hostname or not parsed.netloc:
            return None

        if parsed.username is not None or parsed.password is not None:
            return None

        if parsed.query or parsed.fragment:
            return None

        # Validate the port if one is supplied.
        _ = parsed.port

        return api_base_url.strip().rstrip("/")

    except (TypeError, ValueError):
        return None


def _validate_endpoint(endpoint):
    """
    Accept safe relative API paths, including query parameters.

    Reject absolute URLs, network locations, fragments,
    path traversal, control characters and backslashes.
    """

    if not isinstance(endpoint, str) or not endpoint:
        return None

    # Reject control characters.
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in endpoint
    ):
        return None

    # Reject Windows-style path separators.
    if "\\" in endpoint:
        return None

    try:
        parsed = urlsplit(endpoint)

        # Only relative API paths are allowed.
        if parsed.scheme or parsed.netloc:
            return None

        # Fragments are not valid API endpoint components.
        if parsed.fragment:
            return None

        path = parsed.path

        if not path or path.startswith("//"):
            return None

        # Reject directory traversal.
        if any(part == ".." for part in path.split("/")):
            return None

        normalized_path = "/" + path.lstrip("/")

        # Preserve legitimate query parameters.
        if parsed.query:
            normalized_path += "?" + parsed.query

        return normalized_path

    except (TypeError, ValueError):
        return None


def _validate_timeout(timeout):
    """Require a positive finite numeric timeout."""

    if isinstance(timeout, bool):
        return False

    if not isinstance(timeout, (int, float)):
        return False

    return 0 < timeout < float("inf")


def request_api(
    method,
    endpoint,
    *,
    api_base_url,
    token=None,
    timeout=REQUEST_TIMEOUT,
    request_func=None,
    **kwargs
):
    """
    Execute an API request with safe error handling.

    This module contains no Streamlit dependencies,
    allowing independent unit testing.
    """

    validated_base_url = _validate_base_url(api_base_url)
    validated_endpoint = _validate_endpoint(endpoint)

    if validated_base_url is None or validated_endpoint is None:
        return APIResult(
            error="The API request configuration is invalid."
        )

    if not _validate_timeout(timeout):
        return APIResult(
            error="The API request timeout configuration is invalid."
        )

    if token is not None:
        if (
            not isinstance(token, str)
            or not token.strip()
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in token
            )
        ):
            return APIResult(
                error="The authentication configuration is invalid."
            )

    # Never allow TLS certificate verification to be disabled.
    if "verify" in kwargs and kwargs["verify"] is False:
        return APIResult(
            error="TLS certificate verification cannot be disabled."
        )

    if request_func is None:
        request_func = requests.request

    url = f"{validated_base_url}{validated_endpoint}"

    headers = dict(kwargs.pop("headers", {}) or {})

    # Remove caller-supplied Authorization headers.
    # HTTP header names are case-insensitive.
    headers = {
        key: value
        for key, value in headers.items()
        if not (
            isinstance(key, str)
            and key.lower() == "authorization"
        )
    }

    # Public authentication endpoints do not need a bearer token.
    is_public_auth_endpoint = (
        validated_endpoint.split("?", 1)[0].rstrip("/")
        in PUBLIC_AUTH_ENDPOINTS
    )

    is_authenticated_request = (
        token is not None
        and not is_public_auth_endpoint
    )

    # Only the explicitly supplied token can authorize a request.
    if is_authenticated_request:
        headers["Authorization"] = f"Bearer {token.strip()}"

    if headers:
        kwargs["headers"] = headers

    response = None

    try:
        response = request_func(
            method,
            url,
            timeout=timeout,
            **kwargs
        )

        response.raise_for_status()

        if not response.content:
            return APIResult(data={})

        try:
            return APIResult(data=response.json())

        except ValueError:
            return APIResult(
                error=(
                    "The server returned an invalid response. "
                    "Please try again later."
                )
            )

    except requests.exceptions.HTTPError as exc:
        error_response = exc.response or response

        status_code = getattr(error_response, "status_code", None)

        if status_code == 401 and is_authenticated_request:
            return APIResult(
                error=(
                    "Your session is invalid or has expired. "
                    "Please log in again."
                ),
                unauthorized=True,
            )

        if status_code in SAFE_HTTP_MESSAGES:
            message = SAFE_HTTP_MESSAGES[status_code]

        elif isinstance(status_code, int) and status_code >= 500:
            message = (
                "The server encountered an internal error. "
                "Please try again later."
            )

        else:
            message = (
                "The request could not be completed. "
                "Please try again."
            )

        return APIResult(error=message)

    except requests.exceptions.ConnectionError:
        return APIResult(
            error=(
                "Cannot connect to the application server. "
                "Please check whether the backend is running."
            )
        )

    except requests.exceptions.Timeout:
        return APIResult(
            error=(
                "The request took too long to complete. "
                "Please try again."
            )
        )

    except requests.exceptions.RequestException:
        return APIResult(
            error=(
                "A network error occurred while processing "
                "your request. Please try again."
            )
        )

    except (TypeError, ValueError):
        return APIResult(
            error="The API request could not be processed."
        )
