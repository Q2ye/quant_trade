# -*- coding: utf-8 -*-
"""监控模块告警通知渠道"""

from quant_server.modules.monitor.alerters.email_alerter import EmailAlerter
from quant_server.modules.monitor.alerters.wechat_alerter import WechatAlerter
from quant_server.modules.monitor.alerters.dingtalk_alerter import DingtalkAlerter

__all__ = ["EmailAlerter", "WechatAlerter", "DingtalkAlerter"]
