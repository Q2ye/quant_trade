# -*- coding: utf-8 -*-
"""
微信告警通知渠道

通过企业微信 Webhook 或应用消息发送告警。
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WechatAlerter:
    """企业微信告警渠道"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._webhook_url = cfg.get("webhook_url", "")
        self._corp_id = cfg.get("corp_id", "")
        self._agent_id = cfg.get("agent_id", "")
        self._secret = cfg.get("secret", "")
        self._enabled = bool(self._webhook_url or (self._corp_id and self._agent_id))

    @property
    def channel_name(self) -> str:
        return "wechat"

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, title: str, message: str,
                   recipients: Optional[List[str]] = None) -> bool:
        """发送微信告警"""
        if not self._enabled:
            logger.warning("微信渠道未配置，跳过发送")
            return False

        content = f"{title}\n\n{message}"

        if self._webhook_url:
            return await self._send_via_webhook(content)
        else:
            logger.warning("企业微信应用消息暂未实现，请使用 Webhook")
            return False

    async def _send_via_webhook(self, content: str) -> bool:
        try:
            import aiohttp

            payload = {
                "msgtype": "text",
                "text": {
                    "content": content[:2048],
                },
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        logger.info("企业微信告警已发送")
                        return True
                    else:
                        body = await resp.text()
                        logger.error(f"企业微信发送失败: HTTP {resp.status} {body}")
                        raise RuntimeError(f"企业微信返回 {resp.status}: {body}")

        except Exception as e:
            logger.error(f"微信发送失败: {e}")
            raise
