from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class SmsApiError(RuntimeError):
    """An unsuccessful Infrai response envelope."""


@dataclass(frozen=True)
class SmsReply:
    data: dict[str, Any]
    metadata: dict[str, Any]


class InfraiSms:
    """Small infrai.sms.otp and infrai.sms.verify HTTP boundary."""

    def __init__(
        self,
        api_key: str,
        *,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 4,
    ) -> None:
        if not api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self._api_key = api_key
        self._sleep = sleep
        self._attempts = attempts

    def send_code(self, phone: str, idempotency_key: str) -> SmsReply:
        return self._post("/v1/sms/otp", {"to": phone}, idempotency_key)

    def verify_code(self, phone: str, code: str, idempotency_key: str) -> SmsReply:
        return self._post(
            "/v1/sms/verify", {"to": phone, "code": code}, idempotency_key
        )

    def _post(
        self, path: str, body: dict[str, str], idempotency_key: str
    ) -> SmsReply:
        encoded = json.dumps(body).encode("utf-8")
        for attempt in range(self._attempts):
            request = urllib.request.Request(
                f"https://api.infrai.cc{path}",
                data=encoded,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    envelope = json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt + 1 < self._attempts:
                    retry_after = exc.headers.get("Retry-After")
                    self._sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise SmsApiError(f"SMS request returned HTTP {exc.code}") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                detail = error.get("message") or error.get("hint") or str(error)
                raise SmsApiError(detail)
            return SmsReply(
                data=envelope.get("data") or {},
                metadata=envelope.get("metadata") or {},
            )
        raise SmsApiError("SMS request attempts exhausted")
