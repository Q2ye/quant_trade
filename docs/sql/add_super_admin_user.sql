-- 新增超级管理员用户SQL脚本
-- 执行顺序：先插入用户，再插入相关数据

-- 1. 插入超级管理员用户
INSERT INTO sys_users (
    id,
    username,
    password,
    email,
    phone,
    real_name,
    role,
    is_active,
    last_login,
    created_at,
    updated_at
) VALUES (
    'user_1',
    'superadmin',
    'MTExMTExLmE=', --对应密码：111111.a
    'superadmin@quant.com',
    '13888888888',
    '系统超级管理员',
    'admin',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (username) DO NOTHING;

-- 2. 创建超级管理员角色（如果不存在）
INSERT INTO sys_roles (
    id,
    role_code,
    role_name,
    description,
    is_default,
    permissions
) VALUES (
    'role_1',
    'super_admin',
    '超级管理员',
    '系统最高权限管理员，拥有所有模块的完全控制权限',
    FALSE,
    '["*:*:*"]'::JSONB  -- 通配符权限，表示所有模块的所有操作
)
ON CONFLICT (role_code) DO NOTHING;

-- 3. 将超级管理员用户关联到超级管理员角色
INSERT INTO sys_user_roles (
    id,
    user_id,
    role_id,
    assigned_by,
    assigned_at
)
SELECT
    'user_role_1',
    u.id::VARCHAR,
    r.id::VARCHAR,
    u.id::VARCHAR,  -- 分配人为自己
    CURRENT_TIMESTAMP
FROM sys_users u
CROSS JOIN sys_roles r
WHERE u.username = 'superadmin'
  AND r.role_code = 'super_admin'
ON CONFLICT (user_id, role_id) DO NOTHING;

-- 4. 为用户添加所有模块的完整权限
INSERT INTO sys_permissions (
    id,
    user_id,
    module,
    can_read,
    can_write,
    can_execute
)
SELECT
    'perm_' || row_number() OVER (ORDER BY module_name),
    u.id::VARCHAR,
    module_name,
    TRUE,
    TRUE,
    TRUE
FROM sys_users u
CROSS JOIN (
    VALUES
    ('strategy'), ('basket'), ('trading'), ('market'),
    ('account'), ('analysis'), ('backtest'), ('system'),
    ('user_management'), ('data_management'), ('monitor')
) AS modules(module_name)
WHERE u.username = 'superadmin'
ON CONFLICT (user_id, module) DO UPDATE
SET
    can_read = TRUE,
    can_write = TRUE,
    can_execute = TRUE,
    updated_at = CURRENT_TIMESTAMP;

-- 5. 设置用户偏好
INSERT INTO user_preferences (
    id,
    user_id,
    language,
    timezone,
    theme,
    notification_settings,
    trading_settings,
    display_settings
)
SELECT
    'pref_' || u.id::VARCHAR,
    u.id::VARCHAR,
    'zh-CN',
    'Asia/Shanghai',
    'dark',
    '{"email": true, "wechat": true, "sms": true}',
    '{"default_account": null, "confirm_before_trade": false}',
    '{"default_chart_type": "candle", "show_grid": true}'
FROM sys_users u
WHERE u.username = 'superadmin'
ON CONFLICT (user_id) DO UPDATE
SET
    language = 'zh-CN',
    timezone = 'Asia/Shanghai',
    theme = 'dark',
    notification_settings = '{"email": true, "wechat": true, "sms": true}',
    trading_settings = '{"default_account": null, "confirm_before_trade": false}',
    display_settings = '{"default_chart_type": "candle", "show_grid": true}',
    updated_at = CURRENT_TIMESTAMP;

-- 6. 验证插入结果
SELECT '超级管理员用户创建完成' as status;

-- 查看新创建的用户信息
SELECT
    u.id::VARCHAR as id,
    u.username,
    u.email,
    u.role,
    u.is_active,
    r.role_name,
    r.permissions
FROM sys_users u
LEFT JOIN sys_user_roles ur ON u.id::VARCHAR = ur.user_id
LEFT JOIN sys_roles r ON r.id::VARCHAR = ur.role_id
WHERE u.username = 'superadmin';