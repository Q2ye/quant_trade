// WebSocket连接和消息管理
// 修复 2026-08（A37）：原 handler commit/dispatch 到不存在的 store 模块
// （market/ui 模块不存在），导致实时推送全部失效。改为 safeCommit 安全路由：
// 模块不存在或 mutation 未知时仅告警，不再静默失败/抛错。
import { ref, onUnmounted, onMounted } from "vue";
import { useStore } from "vuex";
import type {
  SignalMessage,
  RealTimeQuoteMessage,
  OrderStatusMessage,
  RiskAlertMessage,
} from "@/types";

interface WebSocketMessage {
  event: string;
  data: any;
  timestamp: number;
}

export function useWebSocket() {
  const store = useStore();
  const ws = ref<WebSocket | null>(null);
  const isConnected = ref(false);
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  const reconnectInterval = ref(3000);
  let reconnectTimer: number | null = null; // 修复 A37-2：卸载后清理重连定时器

  // 修复 2026-08（A37）：安全 commit——模块/mutation 不存在时仅告警不抛错
  const safeCommit = (type: string, payload?: any) => {
    const mod = type.split("/")[0];
    if (!store.hasModule(mod)) {
      console.warn(`[useWebSocket] store 模块不存在: ${mod}（消息已忽略）`);
      return;
    }
    try {
      store.commit(type, payload);
    } catch (e) {
      console.warn(`[useWebSocket] commit 失败: ${type}`, e);
    }
  };

  // 消息处理器映射
  const messageHandlers = {
    market_data: handleMarketData,
    trade_signal: handleTradeSignal,
    order_update: handleOrderUpdate,
    risk_alert: handleRiskAlert,
    system_status: handleSystemStatus,
  };

  // 连接WebSocket
  const connect = () => {
    try {
      const token = store.state.user?.token;
      const wsUrl = `${import.meta.env.VITE_WS_URL}?token=${token}`;

      ws.value = new WebSocket(wsUrl);

      ws.value.onopen = () => {
        console.log("WebSocket连接成功");
        isConnected.value = true;
        reconnectAttempts.value = 0;
        reconnectInterval.value = 3000;
      };

      ws.value.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data);
        handleMessage(message);
      };

      ws.value.onclose = (event) => {
        console.log("WebSocket连接关闭", event);
        isConnected.value = false;
        handleReconnect();
      };

      ws.value.onerror = (error) => {
        console.error("WebSocket错误", error);
        isConnected.value = false;
      };
    } catch (error) {
      console.error("WebSocket连接失败", error);
      handleReconnect();
    }
  };

  // 处理消息
  const handleMessage = (message: WebSocketMessage) => {
    const handler =
      messageHandlers[message.event as keyof typeof messageHandlers];
    if (handler) {
      handler(message.data);
    } else {
      console.warn("未知的消息类型:", message.event);
    }
  };

  // 处理市场数据（dashboard 模块存在 ADD_REALTIME_UPDATE）
  function handleMarketData(data: RealTimeQuoteMessage) {
    safeCommit("dashboard/ADD_REALTIME_UPDATE", data);

    // 更新相关图表（try 保护：trade state 结构变化时不影响主流程）
    try {
      if (store.state.trade?.currentSymbol === data.symbol) {
        safeCommit("trade/UPDATE_CURRENT_PRICE", data);
      }
    } catch (e) {
      console.warn("[useWebSocket] 当前价更新跳过:", e);
    }
  }

  // 处理交易信号
  function handleTradeSignal(data: SignalMessage) {
    safeCommit("strategy/ADD_SIGNAL", data);

    // 显示桌面通知
    try {
      if (Notification.permission === "granted") {
        new Notification("交易信号提醒", {
          body: `${data.symbol} ${data.signalType}信号 - ${data.reason}`,
          icon: "/favicon.ico",
        });
      }
    } catch (e) {
      console.warn("[useWebSocket] 桌面通知失败:", e);
    }
  }

  // 处理订单更新
  function handleOrderUpdate(data: OrderStatusMessage) {
    safeCommit("trade/UPDATE_ORDER_STATUS", data);
  }

  // 处理风险警报（risk 模块实际 mutation 为 ADD_EVENT）
  function handleRiskAlert(data: RiskAlertMessage) {
    safeCommit("risk/ADD_EVENT", data);

    // 修复 A37：ui 模块不存在，改用控制台告警 + 浏览器通知兜底
    console.warn("[风险警报]", data.message);
    try {
      if (Notification.permission === "granted") {
        new Notification("风险警报", {
          body: data.message,
          icon: "/favicon.ico",
        });
      }
    } catch (e) {
      /* ignore */
    }
  }

  // 处理系统状态
  function handleSystemStatus(data: any) {
    safeCommit("system/UPDATE_SYSTEM_STATUS", data);
  }

  // 重连逻辑
  const handleReconnect = () => {
    if (reconnectAttempts.value < maxReconnectAttempts) {
      reconnectAttempts.value++;
      reconnectTimer = window.setTimeout(() => {
        console.log(
          `尝试重新连接... (${reconnectAttempts.value}/${maxReconnectAttempts})`,
        );
        connect();
      }, reconnectInterval.value);

      // 指数退避
      reconnectInterval.value = Math.min(reconnectInterval.value * 1.5, 30000);
    }
  };

  // 发送消息
  const send = (event: string, data: any) => {
    if (ws.value && isConnected.value) {
      const message = {
        event,
        data,
        timestamp: Date.now(),
      };
      ws.value.send(JSON.stringify(message));
    } else {
      console.error("WebSocket未连接，无法发送消息");
    }
  };

  // 订阅数据
  const subscribe = (
    channels: string | string[],
    callback?: (data: any) => void,
  ) => {
    const channelList = Array.isArray(channels) ? channels : [channels];
    send("subscribe", { channels: channelList });
    void callback; // reserved for per-channel callback routing
  };

  // 取消订阅
  const unsubscribe = (channels: string | string[]) => {
    const channelList = Array.isArray(channels) ? channels : [channels];
    send("unsubscribe", { channels: channelList });
  };

  // 关闭连接（修复 A37-2：清理重连定时器，避免卸载后仍触发重连）
  const disconnect = () => {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws.value) {
      ws.value.close();
      ws.value = null;
    }
  };

  onMounted(() => {
    connect();
  });

  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
  };
}
