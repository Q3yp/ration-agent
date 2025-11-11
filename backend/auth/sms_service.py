import asyncio
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests

SMS_ENDPOINT = "https://106.ihuyi.com/webservice/sms.php?method=Submit"


class SMSServiceError(Exception):
    """Raised when the upstream SMS provider rejects a request."""


@dataclass
class SMSProviderConfig:
    """Runtime configuration for the Ihuyi SMS provider."""

    account: str
    password: str
    template_id: str = "320655"
    base_url: str = SMS_ENDPOINT
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> Optional["SMSProviderConfig"]:
        account = os.getenv("IHUYI_SMS_ACCOUNT")
        password = os.getenv("IHUYI_SMS_PASSWORD")
        template_id = os.getenv("IHUYI_SMS_TEMPLATE_ID", "320655")
        base_url = os.getenv("IHUYI_SMS_BASE_URL", SMS_ENDPOINT)
        timeout = float(os.getenv("SMS_HTTP_TIMEOUT", "10"))

        if not account or not password:
            return None

        return cls(
            account=account,
            password=password,
            template_id=template_id,
            base_url=base_url,
            timeout=timeout,
        )


class SMSClient:
    """Async-friendly wrapper for the Ihuyi SMS HTTP API."""

    def __init__(self, config: Optional[SMSProviderConfig]):
        self._config = config

    @property
    def is_configured(self) -> bool:
        return self._config is not None

    @property
    def template_id(self) -> Optional[str]:
        return None if self._config is None else self._config.template_id

    async def send_verification_code(
        self,
        mobile: str,
        code: str,
        *,
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._config:
            raise SMSServiceError("SMS provider is not configured")

        tpl = template_id or self._config.template_id
        payload = {
            "account": self._config.account,
            "password": self._config.password,
            "mobile": mobile,
            "format": "json",
        }

        if tpl:
            payload["templateid"] = tpl
            payload["content"] = code
        else:
            payload["content"] = f"您的验证码是：{code}。请不要把验证码泄露给其他人。"

        response_data = await self._post(payload)
        if response_data.get("code") != 2:
            raise SMSServiceError(response_data.get("msg", "SMS provider rejected the request"))
        response_data["templateid"] = tpl
        return response_data

    async def _post(self, data: Dict[str, Any]) -> Dict[str, Any]:
        def send() -> Dict[str, Any]:
            response = requests.post(
                self._config.base_url, data=data, timeout=self._config.timeout
            )
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                raise SMSServiceError("SMS provider returned invalid JSON") from exc

        # Run the blocking request in a worker thread.
        return await asyncio.to_thread(send)


sms_client = SMSClient(SMSProviderConfig.from_env())
