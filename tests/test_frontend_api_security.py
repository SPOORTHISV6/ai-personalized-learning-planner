import json
import requests
import pytest

from unittest.mock import Mock

from frontend.api_client import request_api


API_BASE_URL = "http://127.0.0.1:8001"


def make_response(
    status_code=200,
    json_data=None,
    content=b'{"message": "success"}'
):
    response = requests.Response()

    response.status_code = status_code
    response._content = content
    response.headers["Content-Type"] = "application/json"

    if json_data is not None:
        response._content = json.dumps(json_data).encode("utf-8")

    return response


def mocked_request(response):
    return Mock(return_value=response)


def test_successful_api_request():
    response = make_response(
        200,
        {"student_id": 1}
    )

    result = request_api(
        "GET",
        "/auth/me",
        api_base_url=API_BASE_URL,
        request_func=mocked_request(response)
    )

    assert result.data == {"student_id": 1}
    assert result.error is None
    assert result.unauthorized is False


def test_authenticated_401_marks_session_unauthorized():
    response = make_response(401)

    result = request_api(
        "GET",
        "/auth/me",
        api_base_url=API_BASE_URL,
        token="invalid-token",
        request_func=mocked_request(response)
    )

    assert result.unauthorized is True
    assert result.data is None
    assert "expired" in result.error.lower()


def test_403_does_not_invalidate_session():
    response = make_response(403)

    result = request_api(
        "GET",
        "/admin/users",
        api_base_url=API_BASE_URL,
        token="valid-token",
        request_func=mocked_request(response)
    )

    assert result.unauthorized is False
    assert "permission" in result.error.lower()


def test_500_does_not_expose_internal_error():
    response = make_response(
        500,
        {
            "detail": "Database password=root; SQL connection failed"
        }
    )

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        token="valid-token",
        request_func=mocked_request(response)
    )

    assert result.error is not None
    assert "Database password" not in result.error
    assert "SQL connection failed" not in result.error


def test_connection_error_is_handled_safely():
    mock = Mock(
        side_effect=requests.exceptions.ConnectionError(
            "Internal connection details"
        )
    )

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        request_func=mock
    )

    assert result.data is None
    assert result.error is not None
    assert "Internal connection details" not in result.error


def test_timeout_is_handled_safely():
    mock = Mock(
        side_effect=requests.exceptions.Timeout(
            "Internal timeout details"
        )
    )

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        request_func=mock
    )

    assert result.data is None
    assert "Internal timeout details" not in result.error


def test_invalid_json_response_is_handled():
    response = make_response(
        200,
        content=b"<html>Invalid response</html>"
    )

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        request_func=mocked_request(response)
    )

    assert result.data is None
    assert "invalid response" in result.error.lower()


def test_empty_response_returns_empty_dictionary():
    response = make_response(
        204,
        content=b""
    )

    result = request_api(
        "DELETE",
        "/study-plan-items/1",
        api_base_url=API_BASE_URL,
        request_func=mocked_request(response)
    )

    assert result.data == {}


def test_authentication_endpoint_does_not_receive_existing_token():
    response = make_response(
        200,
        {"access_token": "new-token"}
    )

    mock = mocked_request(response)

    result = request_api(
        "POST",
        "/auth/login",
        api_base_url=API_BASE_URL,
        token="old-token",
        json={"email": "student@example.com"},
        request_func=mock
    )

    assert result.data == {"access_token": "new-token"}

    sent_headers = mock.call_args.kwargs.get("headers", {})

    assert "Authorization" not in sent_headers


# ============================================================
# NEW URL VALIDATION TESTS
# ============================================================

@pytest.mark.parametrize(
    "base_url",
    [
        "",
        None,
        "ftp://example.com",
        "javascript://example.com",
        "http:///missing-host",
        "http://user:password@example.com",
        "http://example.com?token=secret",
        "http://example.com#fragment",
    ],
)
def test_invalid_api_base_urls_are_rejected(base_url):

    mock = Mock()

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=base_url,
        request_func=mock,
    )

    assert result.data is None
    assert result.error is not None
    mock.assert_not_called()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://evil.example/steal",
        "//evil.example/steal",
        "http://evil.example",
        "/dashboard/../auth/me",
        "/dashboard\\..\\auth\\me",
        "",
    ],
)
def test_unsafe_endpoints_are_rejected(endpoint):

    mock = Mock()

    result = request_api(
        "GET",
        endpoint,
        api_base_url=API_BASE_URL,
        request_func=mock,
    )

    assert result.data is None
    assert result.error is not None
    mock.assert_not_called()


def test_relative_endpoint_is_normalized():

    response = make_response(200, {"ok": True})
    mock = mocked_request(response)

    result = request_api(
        "GET",
        "dashboard",
        api_base_url=API_BASE_URL,
        request_func=mock,
    )

    assert result.data == {"ok": True}
    assert mock.call_args.args[1] == f"{API_BASE_URL}/dashboard"


# ============================================================
# AUTHORIZATION HEADER TESTS
# ============================================================

def test_caller_authorization_header_is_removed_without_token():

    response = make_response(200, {"ok": True})
    mock = mocked_request(response)

    request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        headers={"Authorization": "Bearer attacker-token"},
        request_func=mock,
    )

    sent_headers = mock.call_args.kwargs.get("headers", {})

    assert "Authorization" not in sent_headers


def test_explicit_token_overrides_caller_authorization_header():

    response = make_response(200, {"ok": True})
    mock = mocked_request(response)

    request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        token="trusted-token",
        headers={"Authorization": "Bearer attacker-token"},
        request_func=mock,
    )

    sent_headers = mock.call_args.kwargs.get("headers", {})

    assert sent_headers["Authorization"] == "Bearer trusted-token"


@pytest.mark.parametrize(
    "token",
    [
        "",
        123,
        True,
        [],
        {},
    ],
)
def test_invalid_tokens_are_rejected(token):

    mock = Mock()

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        token=token,
        request_func=mock,
    )

    assert result.error is not None
    mock.assert_not_called()


def test_auth_header_is_removed_for_registration():

    response = make_response(200, {"ok": True})
    mock = mocked_request(response)

    request_api(
        "POST",
        "/auth/register",
        api_base_url=API_BASE_URL,
        token="old-token",
        headers={"Authorization": "Bearer attacker-token"},
        request_func=mock,
    )

    sent_headers = mock.call_args.kwargs.get("headers", {})

    assert "Authorization" not in sent_headers


# ============================================================
# TLS AND TIMEOUT TESTS
# ============================================================

def test_tls_verification_cannot_be_disabled():

    mock = Mock()

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        verify=False,
        request_func=mock,
    )

    assert result.error is not None
    assert "TLS" in result.error
    mock.assert_not_called()


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        True,
        "60",
        None,
    ],
)
def test_invalid_timeout_is_rejected(timeout):

    mock = Mock()

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        timeout=timeout,
        request_func=mock,
    )

    assert result.error is not None
    mock.assert_not_called()


def test_http_error_without_response_is_handled():

    mock = Mock(
        side_effect=requests.exceptions.HTTPError(
            "Internal HTTP error"
        )
    )

    result = request_api(
        "GET",
        "/dashboard",
        api_base_url=API_BASE_URL,
        token="valid-token",
        request_func=mock,
    )

    assert result.data is None
    assert result.error is not None
    assert result.unauthorized is False
    assert "Internal HTTP error" not in result.error