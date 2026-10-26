"""Explicit, fail-closed OpenAI SDK access for semantic workflow helpers."""

from __future__ import annotations

import json
import logging
import os
import traceback
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlsplit

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)


MODEL_NAME = "gpt-6-luna"
OPENAI_TIMEOUT_SECONDS = 30.0
MAX_REQUEST_BYTES = 48 * 1024
T = TypeVar("T")
_LOG_REDACTION_MARKER = "[REDACTED]"


def _redact_log_text(value: str) -> str:
    """Redact current SDK credentials/endpoints without retaining them between records."""
    for secret in (os.environ.get("OPENAI_API_KEY", "").strip(), os.environ.get("OPENAI_BASE_URL", "").strip()):
        if secret:
            value = value.replace(secret, _LOG_REDACTION_MARKER)
    return value


def _install_log_redaction() -> None:
    """Sanitize records at creation so child logger propagation cannot bypass redaction."""
    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "_openai_config_redactor", False):
        return

    def redacting_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = current_factory(*args, **kwargs)
        try:
            record.msg = _redact_log_text(record.getMessage())
        except Exception:
            record.msg = _redact_log_text(str(record.msg))
        record.args = ()
        if record.exc_info:
            try:
                exception_text = "".join(traceback.format_exception(*record.exc_info))
                record.exc_text = _redact_log_text(exception_text)
            except Exception:
                record.exc_text = _LOG_REDACTION_MARKER
        elif record.exc_text:
            record.exc_text = _redact_log_text(record.exc_text)
        if record.stack_info:
            record.stack_info = _redact_log_text(record.stack_info)
        return record

    redacting_factory._openai_config_redactor = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(redacting_factory)


_install_log_redaction()


class OpenAIWorkflowError(Exception):
    """Sanitized API failure with no raw SDK exception or credential details."""

    def __init__(self, error_code: str, status_code: int | None = None) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code

    def as_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {"error_code": self.error_code}
        if self.status_code is not None:
            result["status_code"] = self.status_code
        return result


def _read_configuration() -> tuple[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not api_key:
        raise OpenAIWorkflowError("missing_api_key")
    if not base_url:
        raise OpenAIWorkflowError("missing_base_url")
    try:
        parsed = urlsplit(base_url)
        _ = parsed.port
    except ValueError:
        raise OpenAIWorkflowError("invalid_base_url") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OpenAIWorkflowError("invalid_base_url")
    return api_key, base_url


def _payload_text(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        raise OpenAIWorkflowError("invalid_request_payload") from None


def _make_client(payload: Any) -> tuple[OpenAI, str, str]:
    api_key, base_url = _read_configuration()
    payload_text = _payload_text(payload)
    if len(payload_text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise OpenAIWorkflowError("request_too_large")
    if api_key in payload_text or base_url in payload_text:
        raise OpenAIWorkflowError("sensitive_value_in_request")
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=0,
        )
        return client, api_key, base_url
    except Exception:
        raise OpenAIWorkflowError("client_initialization_failed") from None


def _safe_api_error(error: Exception) -> OpenAIWorkflowError:
    if isinstance(error, AuthenticationError):
        code = "api_authentication_failed"
    elif isinstance(error, PermissionDeniedError):
        code = "api_permission_denied"
    elif isinstance(error, RateLimitError):
        code = "api_rate_limited"
    elif isinstance(error, APITimeoutError):
        code = "api_timeout"
    elif isinstance(error, APIConnectionError):
        code = "api_connection_failed"
    elif isinstance(error, APIStatusError):
        code = "api_status_error"
    else:
        code = "api_request_failed"
    status = getattr(error, "status_code", None)
    return OpenAIWorkflowError(code, status if isinstance(status, int) and not isinstance(status, bool) else None)


def _invoke(payload: Any, operation: Callable[[OpenAI], T]) -> T:
    client, api_key, base_url = _make_client(payload)
    try:
        response = operation(client)
        response_text = _payload_text(response.model_dump(mode="json") if hasattr(response, "model_dump") else response)
        if api_key in response_text or base_url in response_text:
            raise OpenAIWorkflowError("sensitive_value_in_response")
        return response
    except OpenAIWorkflowError:
        raise
    except Exception as error:
        raise _safe_api_error(error) from None
    finally:
        try:
            client.close()
        except Exception:
            pass


def create_decision(input: list[dict[str, str]], questions: list[dict[str, Any]]) -> Any:
    """Call the Decisions API without reasoning, store, or arbitrary option fields."""
    payload = {"input": input, "questions": questions}
    return _invoke(
        payload,
        lambda client: client.decisions.create(model=MODEL_NAME, input=input, questions=questions),
    )


def parse_response(
    *,
    instructions: str,
    input: str,
    text_format: type,
    reasoning_effort: str,
    max_output_tokens: int,
) -> Any:
    """Call Responses.parse with fixed model, explicit effort, and no storage/truncation."""
    payload = {"instructions": instructions, "input": input}
    return _invoke(
        payload,
        lambda client: client.responses.parse(
            model=MODEL_NAME,
            instructions=instructions,
            input=input,
            text_format=text_format,
            reasoning={"effort": reasoning_effort},
            store=False,
            max_output_tokens=max_output_tokens,
            truncation="disabled",
        ),
    )
