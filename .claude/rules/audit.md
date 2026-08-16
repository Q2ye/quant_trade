---
paths: "**"
---

# 代码审计规则（通用层）

> 对任何代码变更执行以下快速检查。后端深度审计（数据流/运行时）见 `audit-backend.md`。

## 🔴 第一步：不等式方向检查（修改任何常量/阈值/条件前强制执行）

> **核心原则：禁止凭直觉"加缓冲更安全"跳过程序化分析。**

对本次修改涉及的**每一个**比较操作（`>` `<` `>=` `<=`），执行以下三步：

```
1. 写出不等式：       估算值 > 现金门槛          ← 修改前的原始形态
2. 标注修改位置：     估算值 > 现金门槛          ← 你要改哪里？
                         ↑
3. 判断方向：
   增大左侧 → 通过变少 → 更严格
   增大右侧 → 通过变多 → 更宽松
```

**验证方法**：口算一组具体数字代入修改前后，确认拦截/通过方向符合预期。

> 示例：上次"资金不足"修复失败是因为在 `estimated > cash` 中增大了 `estimated`（左侧），
> 导致拦截更多而非更少。正确的做法是增大 `cash` 侧（右侧）→ `cash * 1.01`。

## 编码前检查（所有文件）

- [ ] 模块放在正确的层级？（api/core/shared/modules — 严禁反向依赖）
- [ ] 模块间通信仅通过 EventEngine？（严禁直接 import 其他模块）
- [ ] 新增 Repository 在 `shared/database/repositories/` 下？（一表一仓库）
- [ ] Engine 有状态 → 继承 EngineBase；Service 无状态 → 不持有事件引擎？

## 编码后检查（所有文件）

- [ ] `py_compile` 通过 / `vue-tsc --noEmit` 无新增错误
- [ ] **严禁** `except Exception: pass` — 至少 `logger.warning(...)`
- [ ] **严禁** 所有异常统一 500 — 区分 ValueError(409)/NotFound(404)/Forbidden(403)
- [ ] `to_dict()` 无 NaN / Inf（PostgreSQL JSONB 拒绝）
- [ ] 删除/重命名的方法引用已全部更新

## 边界条件检查

- [ ] None：`getattr(obj, "field", default)` 而非 `obj.field`
- [ ] 空集合：`df.empty` 检查后 `.iloc[0]`
- [ ] 除零：分母 `> 0` 保护
- [ ] 负数底数：`total_return <= -1` 阻断开方 NaN

## 禁止项

- 禁止 `x: pd.DataFrame = None`（类型注解与初始化值不一致）
- 禁止预期异常打印 ERROR 级别
- 禁止同一个字段写入多个存储位置（单源原则）
- 禁止多源合并覆盖读取（单源原则）
