### 将警示规则写在首页：警惕：每个策略的有效性只有一到两年，策略要迭代，以适应不同的市场环境
### 一定要有止盈止损规则，并严格执行

> 项目文档索引：`docs/README.md`（核心策略体系 → 业务设计 → 功能设计 → 调研分析 → 归档）
> **系统目标：前期资金快速膨胀 · 高收益优先**（唯一真相源：`docs/01-业务设计/系统目标与投资哲学.md`）
> 系统状态：实盘验证期（v4.0）— ETF 底部 v5 + 低吸轮动 v3 双策略实盘，进攻端为高波动动量 7.1（实盘确认版本）
> 代码现状基线：`docs/01-业务设计/系统建设现状白皮书.md`（模块/引擎/表/策略/前端/API 全部代码实证）

---

## 目录结构

### 后端 `quant_server/`

| 目录 | 用途 |
|:---|:---|
| `api/` | FastAPI 应用：15 个 router、dependencies 注入、WebSocket、中间件 |
| `core/` | 引擎基座：EventEngine / MainEngine / EngineRegistry、事件定义、异常体系 |
| `shared/` | 共享层：database（126 个 Repository 一表一仓）、cache、messaging、sources（Tushare/XT P/Mock）、storage |
| `modules/` | 10 个业务模块：data / market / strategy / risk / trade / backtest / account / analysis / monitor / system（+ `storage/` 模型文件存储） |
| `utils/` | 工具库（日志、时间、通用） |
| `tests/` | pytest 测试（testpaths=["tests"]） |
| `scripts/` `tools/` | 运维与工具脚本 |

### 前端 `quant_web/src/`（55 个页面，中心化组织）

```
src/
├── views/                        # 页面（按业务中心分组）
│   ├── DataCenter/               # 市场行情（Market 9 页）+ 数据同步（DataSync 4 页）
│   ├── StrategyCenter/           # 策略构建/回测/因子/绩效（14 页）
│   ├── TradeCenter/              # 交易工作台/篮子/账户/执行（7 页）
│   ├── Signal/                   # 信号监控/确认/历史/时间轴（4 页）
│   ├── Risk/                     # 风控规则/事件/监控/黑名单（4 页）
│   ├── MonitorCenter/            # 告警中心（1 页）
│   ├── System/                   # 系统管理（6 页）
│   └── Login/Register/Redirect/NotFound
├── api/                          # API 客户端封装
├── components/                   # 组件库（charts / common / data / editors / strategy / trade / ui）
├── composables/                  # Vue3 组合式逻辑
├── router/                       # 路由（routes.ts + guard.ts）
├── store/                        # Vuex 4 状态
├── types/                        # TS 类型定义
├── utils/                        # 工具函数
├── styles/  assets/  locales/  plugins/  directives/  layouts/
```

> 完整页面清单见 `docs/01-业务设计/系统建设现状白皮书.md` §5

---

## 常用命令

### 后端（CWD: `quant_server/`，虚拟环境 `.venv/`）

```bash
python -m quant_server.main --config config.yaml --mode development --port 8080  # 完整启动
uvicorn quant_server.api.main:create_app --factory --reload --port 8080          # 仅 API
pytest                                 # 测试
black . && isort .                     # 格式化
mypy .                                 # 类型检查
```

### 前端（CWD: `quant_web/`）

```bash
pnpm serve          # 开发服务器 (8081, proxy /api → localhost:8080)
pnpm build          # 生产构建
pnpm test:unit      # 单元测试
npx vue-tsc --noEmit  # TypeScript 类型检查
```
