# api/main.py
app = FastAPI(
	title="量化交易平台API",
	description="基于混合架构的量化交易平台",
	version="1.0.0"
)

# 注册中间件
app.add_middleware(CORSMiddleware, **cors_config)
app.add_middleware(AuthenticationMiddleware, **auth_config)

# 注册模块路由
app.include_router(data_router, prefix="/api/events", tags=["数据管理"])
app.include_router(strategy_router, prefix="/api/events", tags=["策略管理"])
app.include_router(trade_router, prefix="/api/events", tags=["交易执行"])
app.include_router(backtest_router, prefix="/api/events", tags=["回测验证"])
app.include_router(monitor_router, prefix="/api/events", tags=["系统监控"])


# WebSocket支持
@app.websocket("/ws")
async def websocket_endpoint (websocket: WebSocket):
	"""WebSocket连接端点"""
	await websocket.accept()

	# 订阅事件
	def on_event (event: Event):
		asyncio.create_task(
			websocket.send_json(event.to_dict())
		)

	# 注册事件处理器
	event_engine = get_event_engine()
	event_engine.register(EventType.MARKET_DATA, on_event)
	event_engine.register(EventType.STRATEGY_SIGNAL, on_event)
	event_engine.register(EventType.ORDER_FILLED, on_event)

	try:
		while True:
			# 保持连接
			await websocket.receive_text()
	except WebSocketDisconnect:
		# 取消注册事件处理器
		event_engine.unregister(EventType.MARKET_DATA, on_event)
		event_engine.unregister(EventType.STRATEGY_SIGNAL, on_event)
		event_engine.unregister(EventType.ORDER_FILLED, on_event)