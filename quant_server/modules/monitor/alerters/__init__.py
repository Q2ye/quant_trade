# -*- coding: utf-8 -*-
"""监控模块告警通知渠道"""

from modules.monitor.alerters.wechat_alerter import WechatAlerter
from modules.monitor.alerters.dingtalk_alerter import DingtalkAlerter

__all__ = ["WechatAlerter", "DingtalkAlerter"]
