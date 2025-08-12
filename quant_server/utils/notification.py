# utils/notification.py
"""
统一通知工具模块
支持邮件、钉钉、企业微信等多种通知方式
"""
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
import requests
import json
import logging
from typing import List, Dict

# 配置日志
logger = logging.getLogger('notification')


class NotificationError(Exception):
    """通知发送异常"""
    pass


class BaseNotifier:
    """通知器基类"""

    def send(self, title: str, content: str) -> bool:
        """发送通知"""
        raise NotImplementedError("子类必须实现send方法")

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            return self.send("连接测试", "这是一条测试通知")
        except Exception as e:
            logger.error(f"通知连接测试失败: {str(e)}")
            return False


class EmailNotifier(BaseNotifier):
    """邮件通知器"""

    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str, receivers: List[str]):
        """
        初始化邮件通知器

        :param smtp_server: SMTP服务器地址
        :param smtp_port: SMTP服务器端口
        :param username: 邮箱用户名
        :param password: 邮箱密码/授权码
        :param receivers: 收件人列表
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.receivers = receivers

        logger.info(f"邮件通知器初始化: 服务器={smtp_server}:{smtp_port}, 发件人={username}")

    def send(self, title: str, content: str) -> bool:
        """发送邮件通知"""
        try:
            # 创建邮件内容
            msg = MIMEText(content, 'plain', 'utf-8')
            msg['Subject'] = f"量化平台通知: {title}"
            msg['From'] = self.username
            msg['To'] = ', '.join(self.receivers)

            # 连接SMTP服务器并发送
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # 启用TLS加密
                server.login(self.username, self.password)
                server.sendmail(self.username, self.receivers, msg.as_string())

            logger.info(f"邮件通知发送成功: {title}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {str(e)}")
            raise NotificationError(f"邮件发送失败: {str(e)}")


class DingTalkNotifier(BaseNotifier):
    """钉钉机器人通知器"""

    def __init__(self, webhook: str):
        """
        初始化钉钉机器人通知器

        :param webhook: 钉钉机器人Webhook地址
        """
        self.webhook = webhook
        logger.info("钉钉通知器初始化")

    def send(self, title: str, content: str) -> bool:
        """发送钉钉通知"""
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"### {title}\n{content}"
                }
            }

            response = requests.post(self.webhook, headers=headers, data=json.dumps(data))
            result = response.json()

            if response.status_code != 200 or result.get('errcode') != 0:
                error_msg = result.get('errmsg', '未知错误')
                raise NotificationError(f"钉钉通知失败: {error_msg}")

            logger.info(f"钉钉通知发送成功: {title}")
            return True
        except Exception as e:
            logger.error(f"钉钉通知发送失败: {str(e)}")
            raise NotificationError(f"钉钉通知发送失败: {str(e)}")


class WeChatNotifier(BaseNotifier):
    """企业微信通知器"""

    def __init__(self, corp_id: str, corp_secret: str, agent_id: int):
        """
        初始化企业微信通知器

        :param corp_id: 企业ID
        :param corp_secret: 应用Secret
        :param agent_id: 应用AgentID
        """
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self.access_token = None
        self.token_expire_time = 0

        logger.info("企业微信通知器初始化")

    def _get_access_token(self) -> str:
        """获取访问令牌"""
        try:
            # 如果令牌未过期，直接返回
            if self.access_token and time.time() < self.token_expire_time:
                return self.access_token

            # 获取新的访问令牌
            url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.corp_secret}"
            response = requests.get(url)
            result = response.json()

            if result.get('errcode') != 0:
                raise NotificationError(f"获取企业微信访问令牌失败: {result.get('errmsg', '未知错误')}")

            # 更新令牌和过期时间
            self.access_token = result['access_token']
            self.token_expire_time = time.time() + result['expires_in'] - 300  # 提前5分钟过期

            return self.access_token
        except Exception as e:
            logger.error(f"获取企业微信访问令牌失败: {str(e)}")
            raise NotificationError(f"获取企业微信访问令牌失败: {str(e)}")

    def send(self, title: str, content: str) -> bool:
        """发送企业微信通知"""
        try:
            access_token = self._get_access_token()
            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

            data = {
                "touser": "@all",
                "msgtype": "textcard",
                "agentid": self.agent_id,
                "textcard": {
                    "title": title,
                    "description": content,
                    "url": "URL",  # 可选：点击卡片跳转的URL
                    "btntxt": "详情"
                }
            }

            response = requests.post(url, json=data)
            result = response.json()

            if result.get('errcode') != 0:
                error_msg = result.get('errmsg', '未知错误')
                raise NotificationError(f"企业微信消息发送失败: {error_msg}")

            logger.info(f"企业微信通知发送成功: {title}")
            return True
        except Exception as e:
            logger.error(f"企业微信消息发送失败: {str(e)}")
            raise NotificationError(f"企业微信消息发送失败: {str(e)}")


class NotificationManager:
    """通知管理器"""

    def __init__(self):
        self.notifiers = []
        self.enabled = True
        logger.info("通知管理器初始化")

    def add_notifier(self, notifier: BaseNotifier):
        """添加通知器"""
        self.notifiers.append(notifier)
        logger.info(f"添加通知器: {type(notifier).__name__}")

    def remove_notifier(self, notifier: BaseNotifier):
        """移除通知器"""
        if notifier in self.notifiers:
            self.notifiers.remove(notifier)
            logger.info(f"移除通知器: {type(notifier).__name__}")

    def send_notification(self, title: str, content: str):
        """发送通知到所有通知器"""
        if not self.enabled or not self.notifiers:
            logger.warning("通知功能已禁用或未配置通知器")
            return False

        success = True
        for notifier in self.notifiers:
            try:
                notifier.send(title, content)
            except Exception as e:
                logger.error(f"通知发送失败: {type(notifier).__name__} - {str(e)}")
                success = False

        return success

    def test_all_connections(self):
        """测试所有通知器的连接"""
        results = {}
        for notifier in self.notifiers:
            try:
                result = notifier.test_connection()
                results[type(notifier).__name__] = result
                status = "成功" if result else "失败"
                logger.info(f"{type(notifier).__name__} 连接测试: {status}")
            except Exception as e:
                results[type(notifier).__name__] = False
                logger.error(f"{type(notifier).__name__} 连接测试失败: {str(e)}")

        return results

    def disable(self):
        """禁用通知"""
        self.enabled = False
        logger.warning("通知功能已禁用")

    def enable(self):
        """启用通知"""
        self.enabled = True
        logger.info("通知功能已启用")


# 全局通知管理器实例
notification_manager = NotificationManager()


def send_notification(title: str, content: str, raise_error: bool = False) -> bool:
    """
    发送通知（全局函数）

    :param title: 通知标题
    :param content: 通知内容
    :param raise_error: 是否在失败时抛出异常
    :return: 是否发送成功
    """
    try:
        return notification_manager.send_notification(title, content)
    except Exception as e:
        logger.error(f"发送通知失败: {str(e)}")
        if raise_error:
            raise NotificationError(f"发送通知失败: {str(e)}")
        return False


def init_notifiers_from_config(config: Dict):
    """
    从配置初始化通知器

    :param config: 通知配置字典
    """
    # 邮件通知
    if 'email' in config:
        email_cfg = config['email']
        try:
            email_notifier = EmailNotifier(
                smtp_server=email_cfg['smtp_server'],
                smtp_port=email_cfg['smtp_port'],
                username=email_cfg['username'],
                password=email_cfg['password'],
                receivers=email_cfg['receivers']
            )
            notification_manager.add_notifier(email_notifier)
        except KeyError as e:
            logger.error(f"邮件通知配置不完整: 缺少字段 {str(e)}")

    # 钉钉通知
    if 'dingtalk' in config:
        ding_cfg = config['dingtalk']
        try:
            ding_notifier = DingTalkNotifier(webhook=ding_cfg['webhook'])
            notification_manager.add_notifier(ding_notifier)
        except KeyError as e:
            logger.error(f"钉钉通知配置不完整: 缺少字段 {str(e)}")

    # 企业微信通知
    if 'wechat' in config:
        wx_cfg = config['wechat']
        try:
            wx_notifier = WeChatNotifier(
                corp_id=wx_cfg['corp_id'],
                corp_secret=wx_cfg['corp_secret'],
                agent_id=wx_cfg['agent_id']
            )
            notification_manager.add_notifier(wx_notifier)
        except KeyError as e:
            logger.error(f"企业微信通知配置不完整: 缺少字段 {str(e)}")

    # 测试所有连接
    test_results = notification_manager.test_all_connections()
    logger.info(f"通知连接测试结果: {test_results}")


def format_signal_notification(signal: Dict) -> str:
    """
    格式化信号通知内容

    :param signal: 信号字典
    :return: 格式化后的通知内容
    """
    symbol = signal.get('symbol', '未知代码')
    signal_type = signal.get('signal_type', '未知信号')
    strategy = signal.get('strategy', '未知策略')
    reason = signal.get('reason', '无说明')
    score = signal.get('score', 0.0)
    time = signal.get('signal_time', '未知时间')

    return (
        f"**股票代码**: {symbol}\n"
        f"**信号类型**: {signal_type}\n"
        f"**策略名称**: {strategy}\n"
        f"**信号评分**: {score:.2f}\n"
        f"**生成时间**: {time}\n"
        f"**信号理由**:\n{reason}"
    )


def format_error_notification(error: Exception, context: str = "") -> str:
    """
    格式化错误通知内容

    :param error: 异常对象
    :param context: 错误上下文
    :return: 格式化后的通知内容
    """
    return (
        f"**错误类型**: {type(error).__name__}\n"
        f"**错误信息**: {str(error)}\n"
        f"**错误上下文**: {context}\n"
        f"**发生时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def send_signal_notification(signal: Dict):
    """发送信号通知"""
    title = f"信号通知: {signal.get('symbol', '未知代码')} - {signal.get('signal_type', '未知信号')}"
    content = format_signal_notification(signal)
    send_notification(title, content)


def send_error_notification(error: Exception, context: str = ""):
    """发送错误通知"""
    title = f"系统错误: {type(error).__name__}"
    content = format_error_notification(error, context)
    send_notification(title, content, raise_error=False)


def send_backtest_completed_notification(strategy_name: str, metrics: Dict):
    """发送回测完成通知"""
    title = f"回测完成: {strategy_name}"

    # 格式化关键指标
    metrics_text = "\n".join(
        f"{key}: {value * 100:.2f}%" if key in ["total_return", "annualized_return", "max_drawdown"]
        else f"{key}: {value:.2f}"
        for key, value in metrics.items()
    )

    content = (
        f"策略回测已完成\n\n"
        f"**策略名称**: {strategy_name}\n"
        f"**关键指标**:\n{metrics_text}"
    )

    send_notification(title, content)


# 测试函数
if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # 示例配置
    config = {
        'email': {
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'your_email@example.com',
            'password': 'your_password',
            'receivers': ['receiver1@example.com', 'receiver2@example.com']
        },
        'dingtalk': {
            'webhook': 'https://oapi.dingtalk.com/robot/send?access_token=your_token'
        },
        'wechat': {
            'corp_id': 'your_corp_id',
            'corp_secret': 'your_corp_secret',
            'agent_id': 1000001
        }
    }

    # 初始化通知器
    init_notifiers_from_config(config)

    # 测试信号通知
    test_signal = {
        'symbol': '600519.SH',
        'signal_type': 'BUY',
        'strategy': '价值策略',
        'reason': 'PE低于行业均值且股息率高于3%',
        'score': 0.92,
        'signal_time': '2023-06-15 15:45:00'
    }
    send_signal_notification(test_signal)

    # 测试错误通知
    try:
        raise ValueError("示例错误")
    except Exception as e:
        send_error_notification(e, "测试错误通知")

    # 测试回测完成通知
    test_metrics = {
        'total_return': 0.356,
        'annualized_return': 0.128,
        'max_drawdown': -0.215,
        'sharpe_ratio': 1.85,
        'win_rate': 0.68
    }
    send_backtest_completed_notification("价值策略", test_metrics)