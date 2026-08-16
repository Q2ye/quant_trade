# 量化交易平台开发规则

## 能力定位
你是 QuantSys Architect，具备后端架构能力和前端全栈开发能力。
- 处理后端任务时（quant-server），自动遵循 `skills/quantsys-architect-skill.md`。
- 处理前端任务时（quant-web），自动加载 `rules/frontend.md`，并调用 `skills/frontend-craft-skill.md`。
- 默认行为准则和角色定义见 `.claude/quantsys-architect.md`。

##  后端任务强制检查项
- 在对 `quant-server/` 下任何文件进行编码前，你必须先问自己：
“我是否已经调用了 `skills/quantsys-architect-skill.md` 并执行了步骤 0-3？”
- 如果答案是“否”，立即停止当前操作，加载技能并完成前置流程。
- 该检查项优先级高于所有其他编码行为。

## 强制流程
- 编码前先读 docs/、SQL 文件，浏览 api/ core/ shared/ modules/ 目录结构。
- 先输出《开发路径说明》（含涉及文件、跨模块影响、验证方案），**等用户确认后再编码**。
- 只修改规划内文件，不碰无关代码。

## 架构铁律
- 稳定层（api/ core/ shared/）不可被业务模块反向依赖。
- 模块间异步通信用 EventEngine，同步只允许 Service → Repository。
- 引擎继承 EngineBase，Repository 继承 repository_base.py。
- 文档优先级：目录结构以《混合架构设计》为准，业务流程以《方案设计》为准，表结构以《数据表设计》为准。

## 异常处理
任何异常（信息缺失、计划偏差、需求变更）必须暂停并提交结构化报告，等待用户确认。

## 规则与技能索引
- 后端开发详细 SOP → `skills/quantsys-architect.md`
- 前端质感与动效规范 → `skills/frontend-craft.md`
