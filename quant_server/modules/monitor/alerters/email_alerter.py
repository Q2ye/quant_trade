# -*- coding: utf-8 -*-
"""
邮件告警通知渠道

通过 SMTP 发送告警邮件。
支持配置 SMTP 服务器、认证信息和默认收件人。
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmailAlerter:
    """邮件告警渠道"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._smtp_host = cfg.get("smtp_host", "")
        self._smtp_port = cfg.get("smtp_port", 587)
        self._username = cfg.get("username", "")
        self._password = cfg.get("password", "")
        self._default_recipients: List[str] = cfg.get("default_recipients", [])
        self._use_tls = cfg.get("use_tls", True)
        self._enabled = bool(self._smtp_host and self._username)

    @property
    def channel_name(self) -> str:
        return "email"

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, title: str, message: str,
                   recipients: Optional[List[str]] = None) -> bool:
        """发送邮件告警"""
        if not self._enabled:
            logger.warning("邮件渠道未配置，跳过发送")
            return False

        recipients = recipients or self._default_recipients
        if not recipients:
            logger.warning("无邮件收件人")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["From"] = self._username
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = title

            msg.attach(MIMEText(message, "plain", "utf-8"))

            loop = __import__("asyncio").get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_sync,
                msg,
                recipients,
            )

            logger.info(f"邮件告警已发送: {title} -> {len(recipients)} 收件人")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            raise

    def _send_sync(self, msg, recipients: List[str]) -> None:
        import smtplib

        if self._use_tls:
            server = smtplib.SMTP(self._smtp_host, self._smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(self._smtp_host, self._smtp_port)

        try:
            server.login(self._username, self._password)
            server.sendmail(self._username, recipients, msg.as_string())
        finally:
            server.quit()
