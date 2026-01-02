"""
账户模块常量定义
包含账户类型、状态、错误码等常量
"""

# 账户类型常量
ACCOUNT_TYPE_CASH = "cash"           # 现金账户
ACCOUNT_TYPE_MARGIN = "margin"       # 信用账户
ACCOUNT_TYPE_SIMULATION = "simulation"  # 模拟账户
ACCOUNT_TYPE_DERIVATIVES = "derivatives"  # 衍生品账户

ACCOUNT_TYPES = [
    ACCOUNT_TYPE_CASH,
    ACCOUNT_TYPE_MARGIN,
    ACCOUNT_TYPE_SIMULATION,
    ACCOUNT_TYPE_DERIVATIVES
]

# 账户状态常量
ACCOUNT_STATUS_ACTIVE = "active"          # 活跃
ACCOUNT_STATUS_FROZEN = "frozen"          # 冻结
ACCOUNT_STATUS_CLOSED = "closed"          # 关闭
ACCOUNT_STATUS_PENDING = "pending"        # 待审核
ACCOUNT_STATUS_SUSPENDED = "suspended"    # 暂停

ACCOUNT_STATUSES = [
    ACCOUNT_STATUS_ACTIVE,
    ACCOUNT_STATUS_FROZEN,
    ACCOUNT_STATUS_CLOSED,
    ACCOUNT_STATUS_PENDING,
    ACCOUNT_STATUS_SUSPENDED
]

# 账户操作错误码
ERROR_ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"          # 账户不存在
ERROR_INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"    # 资金不足
ERROR_ACCOUNT_FROZEN = "ACCOUNT_FROZEN"               # 账户已冻结
ERROR_ACCOUNT_CLOSED = "ACCOUNT_CLOSED"               # 账户已关闭
ERROR_INVALID_OPERATION = "INVALID_OPERATION"         # 无效操作
ERROR_POSITION_EXISTS = "POSITION_EXISTS"             # 持仓已存在
ERROR_POSITION_NOT_FOUND = "POSITION_NOT_FOUND"       # 持仓不存在

# 默认配置
DEFAULT_INITIAL_BALANCE = 1000000.00  # 默认初始资金
MIN_ACCOUNT_BALANCE = 0.00           # 最小账户余额
MAX_SINGLE_DEPOSIT = 10000000.00     # 单次最大存款
MAX_SINGLE_WITHDRAWAL = 10000000.00  # 单次最大取款

# 账户号生成规则
ACCOUNT_NUMBER_PREFIX = "ACC"        # 账户号前缀
ACCOUNT_NUMBER_LENGTH = 10           # 账户号总长度

# 缓存键前缀
CACHE_KEY_ACCOUNT_PREFIX = "events:"          # 账户缓存前缀
CACHE_KEY_POSITION_PREFIX = "position:"        # 持仓缓存前缀
CACHE_KEY_BALANCE_PREFIX = "balance:"          # 资金缓存前缀
CACHE_EXPIRE_ACCOUNT = 300                     # 账户缓存过期时间（秒）
CACHE_EXPIRE_POSITION = 60                     # 持仓缓存过期时间（秒）
CACHE_EXPIRE_BALANCE = 30                      # 资金缓存过期时间（秒）

# 账户字段限制
MAX_ACCOUNT_NAME_LENGTH = 100       # 账户名称最大长度
MAX_ACCOUNT_NUMBER_LENGTH = 50      # 账户号最大长度
MAX_BROKER_NAME_LENGTH = 50         # 券商名称最大长度
MAX_STATUS_REASON_LENGTH = 500      # 状态原因最大长度

# 事件类型
EVENT_ACCOUNT_CREATED = "events.created"        # 账户创建
EVENT_ACCOUNT_UPDATED = "events.updated"        # 账户更新
EVENT_ACCOUNT_STATUS_CHANGED = "events.status_changed"  # 账户状态变更
EVENT_DEPOSIT_SUCCESS = "deposit.success"        # 存款成功
EVENT_WITHDRAW_SUCCESS = "withdraw.success"      # 取款成功
EVENT_INSUFFICIENT_BALANCE = "events.insufficient_balance"  # 资金不足

# 日志消息格式
LOG_FORMAT_ACCOUNT_CREATE = "账户创建成功: {account_number} (用户ID: {user_id})"
LOG_FORMAT_ACCOUNT_UPDATE = "账户更新成功: {account_number}"
LOG_FORMAT_DEPOSIT = "存款成功: {account_number} 金额: {amount}"
LOG_FORMAT_WITHDRAW = "取款成功: {account_number} 金额: {amount}"
LOG_FORMAT_INSUFFICIENT_BALANCE = "资金不足: {account_number} 请求: {requested}, 可用: {available}"