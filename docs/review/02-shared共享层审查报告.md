# 02 shared 共享层审查报告

> 审查基准日期：2026-07（以会话当日为准，待确认）
> 审查范围：`quant_server/shared/` 全部 219 个 .py 文件；重点深读：
> - database/repositories：126 个 repo 文件（base/、query_builder、strategy/、trading/、market/、account/、analysis/、operation/、system/、hyper_tables/、cache/）
> - database/session（session_manager / connection_pool / transaction）、database/models（4 文件，130 个 __tablename__）
> - cache（cache_manager / memory_cache / redis_cache / decorators / serializers / base）
> - messaging（message_bus / producer / consumer / base / serializer / types）
> - sources（base_source / mock_source / xtp_source / tushare_source / baostock_source / source_factory）
> - config（config_manager / constants）、storage（file_storage）、utils（background_executor）、logging（sql_timing / timing）
> 对照基线：`docs/sql/create_table.sql`（GBK 编码，共 131 张 CREATE TABLE）；架构约束见 AGENTS.md/CLAUDE.md（一表一仓、共享层纯数据访问、模块间仅走 EventEngine）
> 审查性质：只读；未修改任何业务代码；所有结论均附 文件:行号 实证；不确定项标注"待确认"

### 审查文件清单（数量统计）

| 目录 | 文件数 | 说明 |
|---|---|---|
| shared/database/repositories | 126 | 其中 base/ 3（repository_base、hyper_repository_base、query_builder），hyper_tables/ 4，cache/ 2，其余按域（strategy 12、trading 13、market 55、account 6、analysis 14、operation 8、system 12） |
| shared/database/models | 4 | business_models.py(57 表)、data_models.py(59 表)、system_models.py(14 表)，合计 130 个 __tablename__ |
| shared/database/session | 3 | session_manager、connection_pool、transaction |
| shared/cache | 6 | base、cache_manager、memory_cache、redis_cache、decorators、serializers |
| shared/messaging | 6 | base、message_bus、producer、consumer、serializer、types |
| shared/sources | 6 | base_source、mock_source、xtp_source、tushare_source、baostock_source、source_factory |
| shared/config | 2 | config_manager(1008 行)、constants |
| shared/storage | 1 | file_storage |
| shared/utils | 1 | background_executor |
| shared/logging | 2 | sql_timing、timing |
| shared/security | 4 | jwt_handler、encryption、password、audit（本次仅旁路确认引用关系） |
| 对照基线 | — | docs/sql/create_table.sql：131 张 CREATE TABLE（GBK 编码，`-- 注释 CREATE TABLE` 同行的写法需整体解码后统计） |

## 1. 业界对比分析

### 1.1 BaseRepository vs SQLAlchemy 2.0 最佳实践

**符合项**：注入 AsyncSession、泛型 `BaseRepository(Generic[T])`、2.0 风格 `select()/update()` 构造、`bulk_upsert`（repository_base.py:352-464）用 `pg_insert().on_conflict_do_update()` 并自动反射冲突键、分块写入防 PG 32767 参数上限——方向与 SQLAlchemy 2.0 + PostgreSQL 最佳实践一致，sync_service 的 50+ 处 bulk_upsert 依赖此路径。

**差距项**：
1. **非原子 upsert**：`upsert()`（repository_base.py:677-714）先 `get_by()` 再决定 update/create，并发时 check-then-act 竞态互相覆盖；业界一律 ON CONFLICT 单语句。`batch_upsert()`（L716-761）虽是 ON CONFLICT，但**恒定返回 `[]`**（L758），契约残缺。
2. **批量插入未走 executemany**：`batch_create()`（L249-282）循环 `session.add()` 后 flush，生成 N 条 INSERT；应 `session.execute(insert(model), data_list)`（executemany 快 5-10 倍）。
3. **session 生命周期越权**：repo 层多处直接 `session.rollback()`（L246/281/315/347/496/520）、`session.commit()`（etf_minute_repo.py:209、strategy_repo.py:349、stock_daily_repo.py:780/813、signal_repo_v2.py:51）；被包在外部事务内会整体回滚/提前提交。最佳实践：repo 层不碰事务边界。
4. **异常吞栈 + 同名异常多份**：全部方法 `except Exception as e: raise RepositoryError(...)` 未 `from e`；RepositoryError 在 types.py:20、repository_base.py:833、utils.py:1114、order_repo.py:1076 存在 3-4 份定义，跨模块 except 捕获失效（见 5）。
5. **分页 count 低效**：`paginate()`（L602-673）用 `select(func.count()).select_from(query.subquery())` 包裹带排序查询。
6. **datetime 转换白名单过窄**：`_convert_record_datetime`（L85-106）只认 13 个固定字段名，`ann_date/expire_date` 等变体不转换，字符串日期直入 Date 列会报错或静默错值。
7. **关联加载误用**：`get()` 的 `with_related`（L127-130）用 `hasattr(self.model, field)` 判断后直接 `joinedload`，普通列属性也通过 hasattr → joinedload 对非 relationship 抛 ArgumentError；应校验 `inspect(model).relationships`。
8. **返回类型不一致**：`get_latest_record(limit>1)`（hyper_repository_base.py:71-101）返回 List 但签名声明 `Optional[T]`，调用方按单对象用会踩坑。

### 1.2 缓存体系 vs functools.lru_cache / Redis 模式

- **MemoryCache**（memory_cache.py：OrderedDict LRU + TTL + tag 反索引 + 清理线程）功能完整可对标 cachetools；但全链路**无 single-flight**、**TTL 无随机抖动**，存在缓存击穿/雪崩风险（业界标配"per-key 锁单飞 + TTL 抖动"）。
- **RedisCache 序列化缺陷**：`_serialize_entry`（redis_cache.py:68-73）把 pickle bytes 塞进 dict 再 `json.dumps` → 恒 TypeError；业界模式是整体 pickle/msgpack + `SETEX`，不存在"JSON 包二进制"。
- **`CacheBase.increment()`**（base.py:176-185）注释"原子递增"实为 get→set 两段式；Redis 场景必须 `INCR`。
- **装饰器事件循环误用**：sync_wrapper / cached_property 用 `asyncio.get_event_loop()` + `run_until_complete`（decorators.py:157-165、187-199、257-284），运行中 loop 内调用即 RuntimeError，且 get 路径只捕 CacheError 导致异常穿透。
- **key 设计缺陷**：方法级 key 对对象参数落 repr（含内存地址，decorators.py:34-39）→ 缓存永不命中；cached_property 用 `id(obj)`（L250）→ id 复用串数据且无清理。
- **KEYS 命令**：redis_cache.py:193-202/209-229/346-375 三处 `KEYS` 全量扫描，O(N) 阻塞生产实例，应 SCAN。
- **并发安全**：MemoryCache 用 RLock 保护基本操作，但 `delete_pattern`/`get_stats` 的遍历+删除在锁内完成、无死锁风险；`__del__`（L372-374）在解释器退出时 join 清理线程，极端情况拖慢退出（低危）。
- **无旁路写一致性**：缓存与 DB 之间没有任何失效协议（写 DB 后主动删 key 的调用点极少），与 CACHE_ASIDE 规范相比欠一致性保障。

### 1.3 消息总线 vs 业界 MQ 抽象

- 抽象层（base.py：Producer/Consumer/Bus 三接口 + 事件/命令/请求响应三模式）结构上对标 aio-pika/aiokafka 封装，但**全库无业务方调用 `get_message_bus()/get_producer()/get_consumer()`**（grep 实证：仅 messaging 内部与 account/managers 类型注解，从不注入实例）。
- 缺失 MQ 核心能力：重试/死信、消费确认语义混乱（RabbitMQ 在 `message.process()` 已 ack/reject 后还可能 nack，consumer.py:242-249）、顺序性、持久化。
- 与核心 EventEngine（core/engines，`_publish_event` 被 10+ 引擎使用）职责重叠：进程内事件已有 EventEngine，跨进程 MQ 未落地。业界规范是"进程内 in-process bus、跨进程才引 MQ"，当前两条线都没闭环（见 5.3）。
- **订阅/发布语义错位**：默认后端 redis 的 `publish_event`（message_bus.py:151-157）走 lpush 队列而非 pubsub → 事件被多个订阅者竞争消费（each message to one consumer），违背 pub/sub 广播语义；且 `DefaultMessageBus.subscriptions`（L76-77）从不登记订阅，`shutdown()`（L93-94）无法真正退订。

### 1.4 配置加载 vs pydantic-settings 规范

- 基本合规：嵌套 Settings + `env_nested_delimiter="__"` + model_validator 二次解析。
- **三层命名不一致（高隐患）**：CLAUDE.md 写 `DEV_DATABASE__*`；代码读 `DB_DEV_HOST/DB_PROD_HOST`（config_manager.py:495-511）；实际 `.env` 是 `DB_HOST/DB_PORT/PROD_DB_*`。当前靠 `os.getenv(..., 默认)` 回退偶然正确；生产 `DB_PROD_HOST` 在 .env 不存在 → 生产库 host 落默认 localhost。
- YAML（defaults/environments 合并 L646-664）与 env validator（L443-481）双通道覆盖同一批字段，改一处漏一处。
- `get_config("system")`（L735）：`settings_dict["ENVIRONMENT"].get("value")` 对 pydantic v2 Enum 对象调 dict 方法 → AttributeError（当前无调用方，潜伏）。
- **env 覆盖顺序**：`ConfigManager.get()`（L678-703）先查 os.environ（key 转大写），任意同名环境变量会遮蔽 config.yaml 与模型字段，属于隐式覆盖源，排障困难。

### 1.5 其他共享组件点评

- **storage/file_storage.py**：本地文件存储实现简单可用，但路径未防 `../` 穿越（见 3）、base_path 依赖 cwd。
- **utils/background_executor.py**：多池线程模型 + 跨线程 EventEngine 桥接设计扎实（main.py 与 backtest 已接入）；但 submit_and_wait 忙等轮询（L204-220）、shutdown 时 gather 未完成协程可能挂死（L276-283）。
- **logging/sql_timing.py**：仅 2 个 debug 计时辅助函数，功能过简但无害。
- **sources/xtp_source.py**：几乎全为 "XTP 不支持…" 占位（L138-397），与 modules/trade/adapters/xtp_adapter.py 的 print 占位同为"未实现"状态，与 BROKER=XTP 配置形成误导。
- **security/（旁路确认）**：jwt_handler/password/encryption/audit 未被列入本次深读范围，仅确认其被 modules/system 引用、无反向依赖违规；其中 jwt_handler.py:72 引用了 cache_manager（见 1.2 的装饰器风险），建议后续单独审查。

## 2. 死代码清单

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|---|---|---|---|
| shared/messaging/*（message_bus.py:20-349 等 6 文件） | 模块 | 全库无业务方调用 get_message_bus/get_producer/get_consumer；仅 account/managers 两处 import MessageProducer 作类型注解且从不注入（account_manager.py:26,38） | 与 EventEngine 合并，删除或降级为适配层 |
| shared/database/repositories/base/query_builder.py:87-344 | 类 | QueryBuilder 仅被自身及两个 `__init__.py` 导出引用，modules/ 零使用；且 filter_many 只实现 EQ/NE（L183-187），其余操作符静默丢弃 | 删除；如需保留，补全操作符并加单测 |
| shared/database/repositories/cache/cache_repo.py:48-498 | 类 | CacheRepository（DB 级二级缓存）仅被 repositories/__init__.py 导出，无业务引用 | 删除 |
| shared/database/repositories/cache/distributed_lock_repo.py:13-178 | 类 | 无业务引用；sync redis 阻塞调用 + 非原子锁（见 3） | 删除或改 redis.asyncio + SET NX EX |
| shared/database/repositories/hyper_tables/*（hyper_table_manager.py:27 等 4 类） | 类 | HyperTableManager/TimeBucketManager/RetentionPolicyManager/ChunkManager 仅被自身与 __init__ 引用，modules/ 零使用 | 待确认启动期是否调用；无则删除 |
| shared/database/session/transaction.py:254-294 NestedTransaction | 类 | 无业务引用（手工 SAVEPOINT 字符串拼接，安全性差） | 删除 |
| shared/database/session/session_manager.py:139-152 SessionScope | 类 | 无业务引用；本身有泄漏缺陷（见 3） | 删除 |
| shared/database/session/transaction.py:160-212 `atomic` 装饰器 | 函数 | 无引用（API 层用 transaction_scope/with_transaction） | 删除或补测试 |
| repositories/utils.py:985-1109 QueryCache | 类 | 无业务引用；本地缓存无界增长 | 删除 |
| repositories/utils.py:433-481 batch_insert | 函数 | return_ids 未实现（L468-471 注释"只是一个示例"）、恒返回 []（L475） | 实现或删除 |
| repositories/utils.py:638-720 model_to_dict/rows_to_dict_list、:867-906 safe_like/build_search_conditions | 函数 | 仅 __init__ 导出，modules/ 无引用 | 删除（safe_like 还有转义顺序 bug，见 4） |
| repositories/utils.py:1114 / types.py:20 / repository_base.py:833 RepositoryError | 类 | 3 份同名异常，跨模块 isinstance 失效 | 三合一，统一从 base 导出 |
| shared/config/config_manager.py:910-954 with_fallback_config/load_config_with_fallback | 函数 | 仅自测入口引用；fallback 返回类型与 ConfigManager 不一致 | 删除 |
| shared/database/repositories/types.py:527-555 CacheStrategy/CacheConfig | 类型 | 无业务引用 | 删除 |
| hyper_repository_base.py:259-362 aggregate_by_interval、repository_base.py:791-806 execute_scalar、cache/base.py:163-174 get_or_set | 方法 | 全库无调用方（待确认） | 无引用则删除或补测试 |
| shared/messaging/serializer.py MsgPackSerializer/PickleSerializer（L77/119） | 类 | 仅 messaging 内部引用 | 随 messaging 处置 |
| shared/cache/serializers.py:72-115 JSONDecoder `__type__` 分支 | 代码 | JSONEncoder（L56-67）从不输出 `__type__` 标记，解码分支永不命中 | 删除或让 Encoder 配套输出 |
| shared/config/config_manager.py:957-1008 自测 main 块 | 代码 | `if __name__ == "__main__"` 打印式自测 | 改 pytest |
| sources/mock_source.py:192-205,219-221,285-287 | 方法 | get_minute_bar/get_tick_data/get_suspended/get_financial_statement 恒返回空 DataFrame 占位 | 标注未实现或补数据 |
| cache/serializers.py:253-272 get_serializer("compressed"/"base64") | 函数 | 包装序列化器工厂无业务引用（待确认） | 无引用则删除 |

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|---|---|---|---|---|
| hyper_repository_base.py:250 `delete_by_time_range` | 调用删除时 | `query.where(and_(*conditions))` 返回值未赋回 query → WHERE 丢弃 → **DELETE 全表**；对照 etf_minute_repo.py:206 重写版正确赋值可确认是缺陷 | 严重 | `query = query.where(...)` + 回归测试；排查全部调用点 |
| hyper_repository_base.py:60,245（上游） | stock_daily_repo.py:342 / stock_daily_basic_repo.py:172,776 / stock_daily_limit_repo.py:179 传 ts_code | 基类只识别 `symbol` 列，StockDaily 等表列名是 ts_code → 过滤条件静默失效 | 严重 | 基类按 `__table__.columns` 自动识别 ts_code/symbol/cal_date |
| redis_cache.py:68-73 `_serialize_entry` | 任何 RedisCache.set() | `json.dumps(entry_dict)` 中 value 为 pickle bytes → TypeError → 恒抛 CacheError；sync_service.py:1964、market_service.py:531 等大量 set 在 Redis 启用时全部失败 | 严重 | 整体 pickle/msgpack 序列化 entry，或 value 先 base64 |
| session_manager.py:146-152 SessionScope | 使用 __aexit__ 时 | `__aexit__` 对**新建**的 `get_session()` 上下文执行，进入的那个 session 永不 commit/close → 连接泄漏 | 高 | 保存进入的 CM 引用并对它 __aexit__；或删除 |
| connection_pool.py:189 health_check | 健康检查 | `await conn.execute("SELECT 1")` 传裸字符串，SQLAlchemy 2.0 抛 ArgumentError（initialize L74 正确用 text()） | 高 | 改 `text("SELECT 1")` |
| connection_pool.py:150 线程池重建 | 后台线程 event loop 变更 | `_old_engine.dispose()` 未 await（AsyncEngine.dispose 是协程）→ 旧池泄漏 + coroutine never awaited | 高 | `_old_engine.sync_engine.dispose()` |
| repository_base.py:450-451 bulk_upsert 死锁重试 | 并发 upsert 死锁(40P01)/序列化冲突(40001) | 重试前 `session.rollback()` 回滚整会话 → 同会话先前已 flush 未提交的 chunk 全丢，重试只补当前 chunk | 高 | begin_nested() savepoint 包单 chunk 重试；或每 chunk 独立提交 |
| cache/decorators.py:157-165,257-284 | 运行中 event loop 内调用被装饰同步函数 | `run_until_complete` 抛 RuntimeError，get 路径只捕 CacheError → 异常穿透 | 高 | 同步函数走同步缓存；或强制异步 |
| cache/decorators.py:250 cached_property | 属性缓存 | key 用 `id(obj)`：对象回收后 id 复用 → 串数据；无失效清理 | 中 | 业务主键替代 id；TTL 兜底 |
| cache/decorators.py:34-39 _make_cache_key | 方法级缓存 | args 含对象时 json.dumps(default=str) 落 repr（含内存地址）→ key 每次不同 → 缓存永远失效 | 中 | 约定稳定 key_func |
| cache_manager.py:146 get_multi_level | loader 为协程函数 | `value = loader()` 未 await，协程对象被当值缓存 | 中 | inspect.iscoroutinefunction 后 await |
| cache/serializers.py:140-171 JSONSerializer | 缓存回读 | datetime 序列化为 iso 字符串、无 __type__ 标记 → 反序列化后类型丢失（datetime 变 str） | 中 | Encoder/Decoder 配套类型标记 |
| config_manager.py:735 get_config("system") | 调用 system 配置 | model_dump() 保留 Enum 对象，`ENVIRONMENT.get("value")` → AttributeError（当前无调用方，潜伏） | 中 | `getattr(env, "value", env)` |
| transaction.py:42-65 TransactionManager.begin | session 已有隐式事务（autobegin） | `session.begin()` 抛 "A transaction is already begun"；SET TRANSACTION 非首句报错 | 中 | 用 begin_nested()/连接级事务语义 |
| config_manager.py:495-511 环境变量命名 | 生产部署 | 代码读 DB_DEV_HOST/DB_PROD_HOST，.env 为 DB_HOST/PROD_DB_*，文档为 DEV_DATABASE__*；靠回退偶然正确 | 中 | 统一命名 + 启动自检 |
| consumer.py:422 KafkaConsumer.consume_one | 消费单条 | `finally` 中 `return None` 覆盖 try 的 return → 恒返回 None | 高 | 删除 finally 中的 return |
| consumer.py:242-249 RabbitMQConsumer.process_message | 消费异常 | `async with message.process()` 已自动 ack/reject，auto_ack=False 时再 nack → 双重确认异常 | 中 | 去掉 process() 或统一 ack 策略 |
| consumer.py:69,238,346 RedisConsumer/RabbitMQConsumer subscription_id | 同队列同回调重复订阅 | `f"{queue_name}_{id(callback)}"` 键冲突 → dict 覆盖，旧任务泄漏继续运行 | 中 | 用 uuid 订阅 id + 引用计数 |
| producer.py:350-358 KafkaProducer.publish | 异步上下文 | `future.get(timeout=10)` 同步阻塞事件循环最长 10s | 中 | 用 aiokafka 异步 producer |
| mock_source.py:223-248,270-283,321-324 | 接口替换 | get_daily_basic 缺 symbol 参数、get_etf_basic 参数名 exchange≠market、is_connected 方法改属性、get_etf_daily 签名不一致 → Liskov 违例 | 中 | 对齐 BaseDataSource 签名 |
| repositories/utils.py:453-458,563-565 | 批量写 | batch_insert/batch_upsert 直接改调用方传入 dict（注入 created_at）→ 数据被污染 | 中 | copy() 后再改 |
| distributed_lock_repo.py:51-59 | 获取锁 | setnx+expire 非原子（崩溃锁永不过期）；无 sleep 忙等 30 次/s | 高 | `SET key val NX EX n` + 指数退避 |
| file_storage.py:48-55,75,98,121 | 上传/下载路径 | `os.path.join(base_path, path)` 未校验 `../` → 可越权读写 base_path 之外 | 高 | 规范化 + realpath 前缀校验 |
| repository_base.py:478-484 delete 软删 | 有 is_deleted 无 updated_at 的模型 | `stmt.values(is_deleted=True, updated_at=...)` 硬编码 updated_at → StatementError | 中 | 按 hasattr 动态组装 values |
| api/dependencies/database.py:232 get_transaction_decorator | 使用 with_transaction 装饰器 | `shared_with_transaction(isolation_level)` 把隔离级别当 func 传入 → 返回的是 wrapper 而非装饰器工厂，`@with_transaction(...)` 用法即坏（当前无调用方） | 中 | 按 session_manager.with_transaction 签名重写工厂 |
| connection_pool.py:42-60 初始化 | jsonb 字段读写 | `json_serializer=JSONEncoder().encode`：Decimal→str、datetime→str 且 JSONDecoder 的 __type__ 分支从不命中 → jsonb 类型信息丢失（Decimal 读出为 str） | 低 | 明确约定 jsonb 只存 JSON 原生类型 |
| consumer.py:71-123 RedisConsumer 消费循环 | disconnect 与任务并发 | `brpop(timeout=1)` 每 1s 唤醒一次的空转循环；running 标志依赖 disconnect 置位，未置位则任务永续 | 低 | 用条件事件/长阻塞 brpop + 显式关闭 |
| repository_base.py:499-521 delete_by | 条件删除 | 无论模型有无 is_deleted 一律硬删除，与 delete() 默认软删（L466-478）语义不一致 | 中 | 与 delete() 对齐软删逻辑 |
| decorators.py:295-348 invalidate_cache | 被装饰函数抛异常 | 先执行后删 key → 函数失败时旧缓存未失效，脏数据残留 | 低 | finally 中删除 |
| memory_cache.py:372-374 __del__ | 解释器退出 | stop_cleanup 中 join(timeout=5) 清理线程，进程退出被拖慢 | 低 | 改为注册 atexit 或 daemon 自退出 |
| background_executor.py:116-163 submit | 信号量不可得 | TaskInfo 状态停在 PENDING 直到重试线程获取信号量 → get_status 短暂失真 | 低 | 提交前即置 QUEUED 状态 |

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|---|---|---|---|
| stock_daily_repo.py:547-553（同样 594-600、639-645） | get_top_gainers/losers/volume_leaders 对每条记录单独查 StockBasic → N+1 | 排行榜查询 10+ 次往返 | 一次 JOIN / IN 批量查 StockBasic |
| repository_base.py:249-282 batch_create / utils.py:510-528 batch_update / strategy_repo.py:561-564 delete_old_strategies | 逐条 add/update/delete 循环 | 大表批量操作 N 条 SQL | session.execute(insert/update, list) executemany；delete 用 in_ |
| repository_base.py:312 update() | UPDATE 后再 `await self.get(id)` 多一次 SELECT | 每条更新 2 次往返 | 依赖同步或 RETURNING |
| strategy_repo.py:427-455 get_strategies_by_parameter 回退路径 | `get_all()` 全表加载后 Python 过滤 | 策略表全扫 + 内存过滤 | 直接走 JOIN 查询路径 |
| redis_cache.py:193-202,209-229,346-375 | clear/delete_pattern/get_stats 使用 KEYS 命令 | O(N) 阻塞生产 Redis | SCAN + pipeline；get_stats 用 INFO/DBSIZE |
| hyper_repository_base.py:345 aggregate_by_interval | `order_by('time_bucket')` 传裸字符串，SQLAlchemy 2.0 需 text() 或列对象（待确认版本行为） | 聚合查询可能抛 ArgumentError | 引用 time_bucket 标签对象 |
| stock_daily_repo.py:279-304 get_batch_by_date_range | limit 默认 10,000,000 全量物化 | 大回测内存 OOM | yield_per 流式 / 分批游标 |
| cache 全模块 + cache_manager.py:116-155 | 无 single-flight / 无 TTL 抖动 | 穿透/雪崩时并发回源打爆 DB | per-key asyncio.Lock 单飞 + TTL 随机抖动 |
| repository_base.py:602-673 paginate | count 用 subquery 包裹带排序查询 | 大结果集 count 慢 | count 独立于 order_by |
| repository_base.py:634-635 paginate like 过滤 | 用户输入含 % _ | `field.like(f"%{value}%")` 未转义通配符 → 宽匹配放大结果集（参数化无注入，但语义被利用） | 低 | 复用 utils.safe_like（先修其转义顺序） |
| connection_pool.py:159-162 线程池 | 每 worker 线程独立 engine（pool_size=2） | 任务多时连接膨胀；close()（L178-182）只 dispose 主 engine | shutdown 时统一 dispose 全部线程池 engine |
| background_executor.py:204-220 submit_and_wait | 信号量不可得时 0.02s 轮询忙等最长 30s | 阻塞调用线程 | 改 condition/queue 唤醒 |
| background_executor.py:276-283 _thread_main finally | 协程挂起不结束 | `run_until_complete(gather(*pending))` 无限等待 → 线程池 shutdown 挂死 | 加超时后 cancel |
| utils.py:867-882 safe_like | 转义顺序错误 | 先转义 %、_ 再转义 \ → 前两步产生的反斜杠被二次转义，LIKE 转义失效 | 先转义反斜杠 |
| repositories/utils.py:559-594 batch_upsert | 每条 SELECT 存在性后再写（N 往返 + 竞态） | 大表批量更新极慢 | pg insert on_conflict 单语句 |
| sync_service.py:1790-1791 | `asyncio.gather(*coros)` worker 数 = ts_codes 数 | 股票数大时瞬间大量协程/HTTP 请求 | 信号量限流 |
| order_repo.py:978-1073 get_order_summary | 8 次独立 count/sum 查询 | 摘要接口 8 次往返 | 合并为 2-3 条聚合 SQL |
| source_factory.py:45-53,67-116 | 每个 service 各自 new DataSourceFactory（sync_service.py:749、market_service.py:474） | 实例缓存互不共享 → TushareSource 被重复实例化、重复鉴权 | 提升为模块级单例 |
| sync_service.py:573 | `from shared.sources.tushare_source import _RATE_LIMITS` | 跨模块 import 私有符号（下划线），耦合内部实现 | 公开导出或提供节流配置 |
| strategy_repo.py:108-202 get_strategy_statistics | 一个方法内 4 条独立聚合 SQL（基础/按类型/按状态/近 7 天） | 统计接口 4 次往返 | 合并为 1-2 条 GROUP BY 聚合 |

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|---|---|---|---|
| **一表一仓覆盖率（对照 create_table.sql 131 表）** | 9 张 SQL 表无模型无 repo：composite_account_snapshots、composite_groups、data_quality_issues、feature_sets、market_state_daily、scheduled_tasks、sys_audit_logs、sys_notifications、sys_operation_logs | 高 | 逐表确认：需要的补 model+repo，不需要的在 DDL 标注废弃 |
| models ↔ SQL 表名不一致 | 模型 `system_notifications` vs SQL `sys_notifications`；`data_quality_metrics` vs SQL `data_quality_issues`；`sys_scheduled_tasks` vs SQL `scheduled_tasks` → 按模型查询命中不存在的表 | 高 | 统一 `__tablename__` 与 DDL；上线前 metadata 对照校验 |
| 模型无 SQL 表 | `company_announcements`、hyper_table_metadata、time_bucket_configs、retention_policies、retention_policy_logs、chunk_metadata 不在 create_table.sql | 中 | 补 DDL 或标注由 hyper 管理器动态创建 |
| 有模型无 repo | etf_index、index_daily、index_weight 三模型无 repo；sync_service.py:2840 直接调 `etf_index_repo`（不存在则 ImportError） | 中 | 补 3 个 repo；核对 sync 引用 |
| repo 重复 | basket_repo.py ×2（operation/basket 与 market/reference 均绑 Basket）、stock_daily_limit_repo.py ×2（market/fundamental 与 market/quote 均绑 StockDailyLimit） | 中 | 合并为一处，防双份漂移 |
| signal_repo 双轨 | signal_repo_v2.py 以**模块级函数**（get_pending_signals/update_signal_status/expire_stale_signals）被 api/routers/signal_router.py 直调，绕过"Repository 类 + 一表一仓"规范，且 L51 在 repo 层 commit | 中 | 并入 SignalRepository 类方法，删除 v2 直调 |
| order_repo.py:21 | `from sqlalchemy.testing.schema import Column` — 引用 SQLAlchemy 测试专用模块 | 高 | 改 `from sqlalchemy import Column` |
| order_repo.py:24+1076 | 本地定义 RepositoryError 覆盖导入同名类 → 按基类 except 捕不到 | 高 | 统一单份异常类 |
| order_repo.py:757-819 search_orders | 先构造 filters（含时间/价格范围）后被弃用，改走 paginate 的 EQ 等值过滤 → 时间/价格范围过滤失效 | 高 | 删除死代码，直传条件列表 |
| order_repo.py:658-703 get_orders_with_trades | JOIN 后再 offset/limit → 分页按 trade 行计数而非 order 行 | 中 | 先对订单分页再取 trades |
| strategy_repo.py:488-509 get_strategy_performance_summary | 返回写死的 0 占位数据（total_return=0、sharpe=0、win_rate=0），无"未实现"标记 → 前端拿到假绩效 | 高 | 未实现前抛 NotImplementedError 或返回 None |
| strategy_repo.py:340-353 update_strategy_parameters | `except ImportError` 永不触发（导入在模块顶部）→ 回退分支死代码；fallback 内 session.commit()（L349）破坏事务边界 | 中 | 删除死分支；commit 上移 |
| messaging vs EventEngine 重复建设 | 模块间通信规范仅 EventEngine（core/engines 的 _publish_event 被 10+ 引擎使用），shared/messaging 三后端抽象零实例化；account_manager.py:114 硬编码 `publish("events.events", event)` 无消费者 | 中 | 明确"进程内=EventEngine、跨进程=MQ"二选一落地 |
| message_bus.py:159-193,249-309 request_response | 订阅队列名 kwargs 对 redis/kafka 后端被丢弃（L189-192）；reply_to 未写入消息体 → 应答方无法回投，恒超时 | 高 | 统一队列命名并携带 correlation_id/reply_to |
| config 环境一致性 | get_config("system")（L735）Enum .get('value') 潜伏 AttributeError；DB_DEV_*/DB_PROD_* 命名与 .env/文档不符 | 中 | 统一命名 + 启动自检 |
| stock_daily_repo.py:788-818 optimize_table_storage | VACUUM ANALYZE 在事务块内执行必然报错；CLUSTER 依赖不存在的索引名 | 中 | autocommit 连接执行维护语句，或移除 |
| 数据源真实性 | xtp_source.py 几乎全为 "XTP 不支持…" 占位（L138-397）；modules/trade/adapters/xtp_adapter.py 全 print 占位 | 中 | 标注未实现；接入真实 XTP SDK 前禁止 BROKER=XTP |
| source_factory.py:142-144 | XTP 默认服务器 IP 硬编码 `115.231.218.73:55310` 于共享层 | 生产地址泄漏进代码库，配置缺失时误连 | 中 | 删除默认值，缺失即报错 |
| 缓存体系双轨 | shared/cache 与 repositories/cache_repo（DB 级缓存，死代码）并存 | 低 | 统一到 shared/cache |
| session 依赖重复实现 | session_manager.py:102-108 get_db_session 与 connection_pool.py:236-250 get_db_session 功能重复（两个同名依赖注入器） | 低 | 收敛为 session_manager 一处 |
| repositories/__init__.py:769-824 | 动态导入失败时静默置 None（try/except 兜底）→ 类缺失不报错，运行时才 AttributeError | 低 | 失败即抛 ImportError |
| hyper_repository_base.py:133-138 batch_insert | `record = self._convert_record_datetime(record)` 循环变量重绑定，转换结果被丢弃 → datetime 转换与 created_at 注入全部失效 | 高 | `chunk[i] = self._convert_record_datetime(chunk[i])` |
| stock_daily_repo.py:773-777 create_partitioned_index | `index_type` 参数 f-string 拼入 DDL | 若参数来自配置/外部输入可注入 DDL 语句（当前仅内部调用） | 低 | 白名单校验 index_type 取值 |
| mock_source.py:308 get_trade_cal | pretrade_date 逻辑：周一（weekday=0）时回退 1 天得到周日（非交易日） | 低 | 用上一交易日历表 | 

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|---|---|---|---|---|---|
| 1 | 严重 | 业务bug | hyper_repository_base.py:250 | delete_by_time_range 的 where 结果被丢弃 → 无条件 DELETE 全表 | `query = query.where(...)` + 回归测试；排查调用点 |
| 2 | 严重 | 业务bug | redis_cache.py:68-73 | RedisCache.set 把 pickle bytes 塞 JSON 恒抛 TypeError，Redis 启用后全链路缓存写入失败 | 整体 pickle/msgpack 序列化 entry |
| 3 | 高 | 边界 | connection_pool.py:189 | health_check 裸字符串 execute，SQLAlchemy 2.0 报错 | 改 text("SELECT 1") |
| 4 | 高 | 边界 | connection_pool.py:150 | 线程池重建时 dispose() 协程未 await，连接池泄漏 | `sync_engine.dispose()` |
| 5 | 高 | 边界 | repository_base.py:450-451 | 死锁重试 rollback 整会话 → 先前 chunk 静默丢失 | savepoint 粒度重试 |
| 6 | 高 | 业务bug | order_repo.py:1076(+24) | 本地 RepositoryError 遮蔽导入类，异常无法被上层捕获 | 统一单份异常类 |
| 7 | 高 | 业务bug | order_repo.py:757-819 | search_orders 构造的 filters 被弃用，时间/价格范围过滤失效 | 删除死代码，直传条件 |
| 8 | 高 | 业务bug | consumer.py:422 | KafkaConsumer.consume_one finally return None 恒覆盖返回值 | 移除 finally return |
| 9 | 高 | 边界 | session_manager.py:146-152 | SessionScope 对新建 CM 调 __aexit__，实际会话泄漏 | 保存原 CM 或删除 |
| 10 | 高 | 性能 | stock_daily_repo.py:547-553 | 排行榜 N+1 查询 StockBasic | JOIN/IN 批量 |
| 11 | 高 | 业务bug | 一表一仓覆盖 | 9 张 SQL 表无 model/repo（含 sys_notifications 等） | 补建或标注废弃 |
| 12 | 高 | 业务bug | models vs SQL | system_notifications/data_quality_metrics/sys_scheduled_tasks 表名不一致 | 统一 __tablename__ |
| 13 | 高 | 边界 | decorators.py:157-165 | 运行 loop 内 run_until_complete 抛 RuntimeError 穿透 | 同步路径改同步缓存 |
| 14 | 高 | 业务bug | strategy_repo.py:488-509 | 绩效摘要返回写死 0 假数据 | 改抛 NotImplementedError |
| 15 | 高 | 边界 | distributed_lock_repo.py:51-59 | setnx+expire 非原子、忙等 30 次/s | SET NX EX |
| 16 | 高 | 边界 | file_storage.py:48-55 | 路径未校验 ../，可越权读写 | realpath 前缀校验 |
| 17 | 高 | 业务bug | message_bus.py:189-192,294 | 响应队列订阅名被丢弃 + reply_to 丢失 → request_response 恒超时 | 统一队列名与消息头 |
| 18 | 高 | 业务bug | hyper_repository_base.py:133-138 | batch_insert datetime 转换结果被丢弃 | 写回 chunk 元素 |
| 19 | 中 | 业务bug | order_repo.py:21 | 导入 sqlalchemy.testing.schema | 改标准导入 |
| 20 | 中 | 性能 | repository_base.py:249-282 | batch_create 逐条 INSERT 无 executemany | session.execute(insert, list) |

### 严重度分布统计

| 严重度 | 数量 | 集中维度 |
|---|---|---|
| 严重 | 2 | 全表删除风险（hyper_repository_base.py:250）、RedisCache 写入不可用（redis_cache.py:68-73） |
| 高 | 13 | 连接/session 泄漏（connection_pool.py:150,189、session_manager.py:146）、死锁重试丢数据、异常类重复（order_repo.py:1076）、过滤失效（order_repo.py:757、hyper_repository_base.py:60）、消息消费恒 None（consumer.py:422）、request_response 恒超时、锁非原子（distributed_lock_repo.py:51）、路径穿越（file_storage.py:48）、N+1（stock_daily_repo.py:547）、表覆盖缺口 9 张、表名不一致 3 组、假绩效数据（strategy_repo.py:488）、batch_insert 转换丢弃（hyper_repository_base.py:133） |
| 中 | 18 | 命名不一致、事务边界越权、KEYS 阻塞、JSON 类型丢失、装饰器 key 失效、DDL/维护语句错误等 |
| 低 | 10 | 退出拖慢、状态失真、通配符放大、占位实现等 |

---
### 五维结论速览

| 维度 | 结论 | 代表问题 |
|---|---|---|
| 1 业界对比 | 基座方向正确，批量写入/配置骨架达标；事务边界与缓存序列化偏离规范 | upsert 非原子、RedisCache 序列化、事务越权 |
| 2 死代码 | 约 1500+ 行无业务引用 | messaging 全模块、QueryBuilder、cache_repo、hyper_tables 管理类 |
| 3 边界情况 | 泄漏与数据丢失类问题集中 | session 泄漏、dispose 未 await、死锁重试丢 chunk、全表删除 |
| 4 性能问题 | N+1 与批量低效为主 | 排行榜 N+1、逐条 INSERT、KEYS 阻塞、无单飞 |
| 5 业务闭环 | 表/模型/repo 三层覆盖存在 12+ 处缺口，双消息体系未闭环 | 9 表无 repo、3 组表名不一致、messaging vs EventEngine |

**审查方法与工具**：静态阅读 + 全库 grep/ripgrep 交叉验证（死代码以"modules/ 无引用"为准）、create_table.sql 以 GBK 解码后正则提取 131 张 CREATE TABLE、模型以 `__tablename__` 提取 130 张、repo 以 `super().__init__(session, Model)` 绑定关系逐一对表；SQLAlchemy 版本行为类结论（裸字符串 execute/order_by、AsyncEngine.dispose 协程、pydantic model_dump Enum 行为）标注"待确认"的均未实际运行验证，建议在修复前用 venv 复现。

**审查结论（摘要）**：共享层基座方向正确（async SQLAlchemy + 泛型 repo + ON CONFLICT 批量写入），但存在 2 个严重缺陷（hyper 删除条件失效可致全表删除、RedisCache 序列化不可用）、约 15 项高危边界/业务问题（session 与连接池泄漏、死锁重试丢数据、异常类多份重复致捕获失效、request_response 恒超时、batch_insert 转换丢弃、路径穿越），约 1500+ 行死代码（messaging 全模块、QueryBuilder、cache_repo、distributed_lock、hyper_tables 管理类、NestedTransaction/SessionScope/atomic 等），以及一表一仓覆盖缺口（9 表无模型无 repo、3 模型无 repo、3 组表名不一致、2 组 repo 重复、signal_repo_v2 绕过规范直调）。

**建议执行顺序**：① 先为两条严重路径（delete_by_time_range、RedisCache.set）补回归测试并修复；② 修复连接池/session 泄漏与死锁重试丢数据；③ 统一 RepositoryError 与表名命名；④ 清理死代码（预估可减 1500+ 行）；⑤ 将"models ↔ create_table.sql"自动对照校验纳入 CI。

---
## 7. 业界标准对照（判定依据映射）

> 本节把第 1-6 章已报告的问题逐一映射到业界公认代码审查标准，作为问题成立与修复优先级的判定依据。
> 约定：SQLA2.0 = SQLAlchemy 2.0 官方最佳实践；EffPy = Effective Python（Brett Slatkin）；CR-Google = Google 代码审查规范（Code Health/可读性/变更规模）；Clean = Clean Code（Robert C. Martin）；SOLID = 单一职责/开闭/里氏替换/接口隔离/依赖倒置；Fowler = 《重构》坏味道清单；PEP8 = PEP 8；OWASP/CWE = OWASP Top 10 / CWE 条目。

### 7.1 引用标准体系

| 标准 | 判定要点（本报告用到的） |
|---|---|
| Google Code Review（Code Health/可读性） | 不做无关重构、不提交死代码/未用抽象、CL 变更范围收敛、命名与注释表达"为什么"、可读性优先于炫技 |
| Clean Code | 函数单一职责、小函数、命名自解释、注释解释意图不解释行为、不返回假数据/隐藏错误、依赖方向清晰 |
| SOLID | SRP：类/模块单一职责；LSP：子类必须可替换基类（签名一致）；DIP：高层不依赖低层具体实现 |
| Fowler《重构》坏味道 | Long Method、Duplicated Code、Dead Code、Lazy Class、Speculative Generality、Feature Envy、Shotgun Surgery、Data Clumps、Message Chains、Primitive Obsession |
| PEP 8 / Effective Python | 命名规范；异常处理（raise from、避免裸 except、异常类命名一致）；上下文管理器 __enter__/__exit__ 配对；协程必须 await；try/finally 不吞返回值；不重复造轮子 |
| SQLAlchemy 2.0 官方最佳实践 | 语句不可变（where/order_by 必须赋回）；文本 SQL 必须 text()；异步 API 必须 await（AsyncEngine.dispose 等）；Session 生命周期归调用方、repo 不碰事务边界；批量写用 executemany；N+1 用 selectinload/joinedload/join；ON CONFLICT 替代 check-then-act；URL 用 URL.create 防特殊字符 |
| OWASP Top 10 / CWE | A03 注入类（CWE-89 SQL 注入、CWE-78 命令注入）；CWE-22 路径遍历；CWE-502 不安全反序列化；A02 认证失效、A06 敏感数据暴露（硬编码地址/密钥） |

### 7.2 问题 → 标准 映射表

| 问题（第 1-6 章位置） | 依据标准 | 判定说明 |
|---|---|---|
| hyper_repository_base.py:250 DELETE 条件丢弃 | SQLA2.0（语句不可变）、Clean（正确性） | Select/Update 构造不可变，where() 返回新对象；弃用返回值 = 无条件 DML，违反 SQLAlchemy 2.0 官方 API 契约 |
| redis_cache.py:68-73 序列化 bytes 进 JSON | EffPy（序列化边界）、SQLA2.0 同族（Redis 官方建议整体序列化） | 序列化器输出类型假设错误；pickle/msgpack 与 JSON 不可混装 |
| connection_pool.py:189 裸字符串 execute | SQLA2.0（text() 必用） | 2.0 迁移指南明确移除字符串隐式 text() 支持 |
| connection_pool.py:150 dispose 未 await | EffPy（协程必须 await）、SQLA2.0（AsyncIO 文档） | AsyncEngine.dispose 是协程，不 await = 资源泄漏 |
| bulk_upsert 死锁重试 rollback（L450-451） | SQLA2.0（事务语义）、Clean（正确性） | session.rollback() 回滚整个会话事务，非 savepoint 粒度，与官方事务指南相悖 |
| order_repo.py:1076 RepositoryError 遮蔽 | PEP8/EffPy（异常类一致命名）、Clean（命名唯一性） | 同名类遮蔽导入，违反"异常类型可被调用方捕获"的基本契约 |
| order_repo.py:757-819 search_orders 死代码分支 | Fowler（Dead Code、Speculative Generality） | 构造后弃用的 filters 属于未使用代码路径 |
| consumer.py:422 finally 中 return | EffPy（try/finally 语义） | finally 的 return 覆盖 try 返回值，隐蔽缺陷（Python 语言规范明确） |
| session_manager.py:146-152 SessionScope | EffPy（上下文管理器配对）、SQLA2.0（Session 生命周期） | __enter__/__exit__ 必须作用于同一 CM 实例；违反 Session per request 规范 |
| stock_daily_repo.py:547-553 N+1 | SQLA2.0（N+1 规避）、Fowler（性能反模式） | 循环内查询应改为 join/selectinload |
| 一表一仓 9 表缺口 | SOLID（SRP）、CR-Google（变更范围） | 数据访问层未覆盖全部聚合根，职责划分不完整 |
| 表名不一致（system_notifications 等 3 组） | Clean（命名一致性）、PEP8 | 命名漂移导致运行时命中不存在的表 |
| decorators.py:157-165 run_until_complete | EffPy（asyncio 正确用法 Item 52/53） | 运行中事件循环内禁止 run_until_complete |
| strategy_repo.py:488-509 假绩效数据 | Clean（不隐藏错误、不返回假数据）、CR-Google（诚实代码） | 写死 0 值让调用方误判业务真实状态 |
| distributed_lock_repo.py:51-59 非原子锁 | Redis 官方分布式锁指南（Redlock/SET NX EX）、OWASP 相邻（并发安全） | setnx+expire 两步非原子，锁永不过期风险 |
| file_storage.py:48-55 路径穿越 | OWASP/CWE-22（路径遍历） | 未规范化用户路径即拼接，属 CWE-22 典型形态 |
| message_bus.py:189-192,294 request_response 契约断裂 | Clean（接口契约）、CR-Google（可读性） | 队列名/应答地址未随消息传递，调用方无法闭环 |
| hyper_repository_base.py:133-138 转换丢弃 | EffPy（变量绑定语义）、Clean（正确性） | 循环变量重绑定不写回容器，属隐蔽逻辑错误 |
| batch_create 逐条 INSERT | SQLA2.0（executemany 性能） | 官方性能指南推荐 executemany 批量参数化 |
| order_repo.py:21 导入 sqlalchemy.testing | Clean（依赖方向）、PEP8 | 生产代码不得依赖测试专用模块 |
| messaging 全模块死代码 + 与 EventEngine 双轨 | Fowler（Dead Code、Speculative Generality）、SOLID（SRP）、CR-Google（避免重复抽象） | 未使用的三层抽象 + 与既有事件机制职责重叠 |
| QueryBuilder/cache_repo/distributed_lock/hyper_tables 管理类 | Fowler（Lazy Class、Speculative Generality） | 无业务引用的"未来可能用"类 |
| utils.py safe_like 转义顺序 | OWASP/CWE-89 相邻（LIKE 转义）、Clean（正确性） | 转义顺序错误导致通配符语义失真（参数化已防注入，非注入漏洞） |
| PickleSerializer 默认反序列化 | OWASP/CWE-502（不安全反序列化） | pickle 反序列化不可信数据存在代码执行风险；缓存值虽自产，仍应审计输入源 |
| xtp_source / xtp_adapter 占位实现 | CR-Google（代码健康：半成品不放主干）、Clean（不隐藏未实现） | "未实现"应以显式异常/特性开关表达，而非静默占位 |
| 硬编码 XTP IP（source_factory.py:142） | OWASP A06（敏感数据暴露）、CR-Google | 生产地址不得硬编码进代码库 |
| RepositoryError 未 from e 吞栈 | EffPy（raise from 链式异常）、PEP8 | 异常链丢失原始上下文，排障困难 |
| config 三层命名不一致 | Clean（命名一致性）、CR-Google | 文档/代码/实际配置三方漂移，违反单一事实来源 |
| get_transaction_decorator 装饰器工厂误用 | EffPy（装饰器工厂契约）、Clean（函数契约） | 把装饰器当工厂调用，签名不匹配即产生坏行为 |
| delete() 软删硬编码 updated_at | Clean（正确性） | 字段存在性假设未校验，模型缺列即报错 |
| paginate like 通配符未转义 | OWASP/CWE-89 相邻、Clean（正确性） | 参数化防注入，但 %/_ 通配符放大结果集 |
| signal_repo_v2 绕过 Repository 规范 | SOLID（SRP）、CR-Google（架构一致性） | 模块级函数直调 + repo 层 commit，破坏一表一仓与事务边界 |
| TimeRange/接口签名不一致（mock_source） | SOLID（LSP） | 子类方法签名/属性形态与基类不一致，不可替换 |
| repository 内含业务方法（技术指标/完整性检查） | Clean（函数单一职责）、SOLID（SRP） | 数据访问层混入计算逻辑，违反"Repository 纯 CRUD"约束 |
| 配置/缓存/消息装饰器宽异常捕获 | PEP8/EffPy（异常粒度） | 宽 except 掩盖真实错误，应精确捕获 |

### 7.3 标准覆盖统计

| 标准 | 命中问题数 | 代表问题 |
|---|---|---|
| SQLAlchemy 2.0 官方最佳实践 | 8 | 删除条件丢弃、裸字符串 SQL、dispose 未 await、死锁回滚粒度、N+1、executemany、Session 生命周期 |
| Fowler《重构》坏味道 | 7 | 死代码簇、Speculative Generality（messaging/QueryBuilder）、Lazy Class |
| Clean Code / SOLID | 12 | 假数据、依赖方向、命名漂移、SRP 越界、LSP 签名不一致 |
| Effective Python / PEP 8 | 8 | finally return、协程 await、run_until_complete、raise from、上下文管理器配对 |
| OWASP Top 10 / CWE | 5 | CWE-22 路径遍历、CWE-502 反序列化、CWE-89 相邻、A06 硬编码地址 |
| Google Code Review | 5 | 半成品占位、重复抽象、架构一致性、变更范围 |

> 说明：本节仅为判定依据映射，不改变第 1-6 章任何结论；标注"待确认"的问题其标准依据同样成立，仅影响严重度评估时机。
