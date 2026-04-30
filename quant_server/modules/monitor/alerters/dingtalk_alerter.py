# -*- coding: utf-8 -*-
"""
钉钉告警通知渠道

通过钉钉机器人 Webhook 发送告警消息。
支持文本和 Markdown 格式。
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DingtalkAlerter:
    """钉钉告警渠道"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._webhook_url = cfg.get("webhook_url", "")
        self._secret = cfg.get("secret", "")
        self._enabled = bool(self._webhook_url)

    @property
    def channel_name(self) -> str:
        return "dingtalk"

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, title: str, message: str,
                   recipients: Optional[List[str]] = None) -> bool:
        """发送钉钉告警"""
        if not self._enabled:
            logger.warning("钉钉渠道未配置，跳过发送")
            return False

        try:
            import time
            import hmac
            import hashlib
            import base64
            import aiohttp

            sign_params = ""
            if self._secret:
                timestamp = str(round(time.time() * 1000))
                sign = self._calculate_sign(timestamp)
                sign_params = f"&timestamp={timestamp}&sign={sign}"

            url = f"{self._webhook_url}{sign_params}" if sign_params else self._webhook_url

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"## {title}\n\n{message}\n\n> 发送时间: {__import__('datetime').datetime.now().isoformat()}",
                },
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("errcode") == 0:
                            logger.info("钉钉告警已发送")
                            return True
                        else:
                            logger.error(f"钉钉返回错误: {result}")
                            raise RuntimeError(f"钉钉错误: {result.get('errmsg', 'unknown')}")
                    else:
                        body = await resp.text()
                        logger.error(f"钉钉发送失败: HTTP {resp.status} {body}")
                        raise RuntimeError(f"钉钉返回 {resp.status}")

        except Exception as e:
            logger.error(f"钉钉发送失败: {e}")
            raise

    def _calculate_sign(self, timestamp: str) -> str:
        import time
        import hmac
        import hashlib
        import base64
        import urllib.parse

        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return urllib.parse.quote_plus(base64.b64encode(hmac_code))
