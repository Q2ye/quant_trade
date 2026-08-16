---
paths: "quant_server/**/*.py"
---

# 后端深度审计规则

> 通用检查见 `audit.md`。本规则仅在后端 Python 文件变更时加载。

## 数据流追踪（涉及持久化时必须执行）

对每个新增/修改字段，画出：**写入位置 → 存储位置 → 读取位置**。

- **写入路径**：严禁同一字段写多个存储位置（如 config JSONB + 参数表双写）
- **读取路径**：严禁从多源合并读取（统一从一个位置读）
- **写入失败兜底**：rollback/except pass 后，后续读取不能拿到不一致数据

## 查询模式检查

- **严禁 N+1 查询**：`for` 循环内是否有 `await db.execute()`？批量查询用 `WHERE ts_code = ANY(:symbols)`
- **严禁逐条写入**：用 `insert().values([...])` 而非逐条 `add()`
- **严禁隐式 lazy load**：关联数据用 `selectinload`/`joinedload` 预加载
- 分页限制：默认 ≤ 100，最大 ≤ 1000

## 算法复杂度检查

- **严禁 O(N²)**：嵌套遍历全量数据（≥1000 元素必须优化）
- **严禁循环内全量扫描**：`max()`/`sum()` 移到循环外 O(1) 追踪
- **严禁多余排序**：`sort_values` 只在必要时执行一次
- **严禁不必要拷贝**：DataFrame `.copy()` 导致双倍内存

## 运行时检查

- **严禁** `asyncio.gather` 共用同一 session（异步 session 不支持并发）
- **严禁** HTTP 请求 session 用于后台任务（响应后 session 已关闭）
- **严禁** 大对象不释放：DataFrame、缓存 dict 使用后清理
- `commit()` 失败必须有回滚 + 日志
- JSON 字段不超限（超长 equity_curve > 10MB 需分页）

## 金融数据精度

- NAV 漂移 < 1e-8
- 前复权因子一致性：相对误差 < 1e-6
- NaN 传播阻断：`**` 运算前检查底数 > 0
- 金额使用 Decimal，不使用 float
