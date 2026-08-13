// 交易执行逻辑
import { ref } from "vue";
import { useStore } from "vuex";
import { useWebSocket } from "./useWebSocket";
import type { Trade, Position } from "@/types";
import type { PlaceOrderRequest } from "@/types";

export function useTrade() {
  const store = useStore();
  const { send } = useWebSocket();

  const isTrading = ref(false);
  const pendingOrders = ref<PlaceOrderRequest[]>([]);

  // 快速下单
  const quickOrder = async (order: {
    ts_code: string;
    direction: "buy" | "sell";
    order_type: "limit" | "market";
    price?: number;
    volume: number;
  }) => {
    if (isTrading.value) {
      throw new Error("有交易正在执行，请稍后重试");
    }

    isTrading.value = true;

    try {
      // 验证交易参数
      await validateOrder(order);

      // 创建订单请求
      const orderId = generateOrderId();
      const orderRequest: PlaceOrderRequest = {
        symbol: order.ts_code,
        direction: order.direction,
        orderType: order.order_type,
        price: order.price,
        volume: order.volume,
      };

      // 添加到待处理订单列表（附加本地元数据）
      pendingOrders.value.push(orderRequest as any);

      // 发送订单到服务器
      send("place_order", { ...orderRequest, order_id: orderId });

      // 更新本地状态
      store.commit("trade/ADD_PENDING_ORDER", {
        ...orderRequest,
        order_id: orderId,
      });

      return orderId;
    } catch (error) {
      console.error("下单失败:", error);
      throw error;
    } finally {
      isTrading.value = false;
    }
  };

  // 市价单
  const marketOrder = (
    ts_code: string,
    direction: "buy" | "sell",
    volume: number,
  ) => {
    return quickOrder({
      ts_code,
      direction,
      order_type: "market",
      volume,
    });
  };

  // 限价单
  const limitOrder = (
    ts_code: string,
    direction: "buy" | "sell",
    price: number,
    volume: number,
  ) => {
    return quickOrder({
      ts_code,
      direction,
      order_type: "limit",
      price,
      volume,
    });
  };

  // 撤单
  const cancelOrder = async (orderId: string) => {
    try {
      send("cancel_order", { order_id: orderId });

      // 更新本地状态
      store.commit("trade/UPDATE_ORDER_STATUS", {
        order_id: orderId,
        status: "cancelling",
      });

      return true;
    } catch (error) {
      console.error("撤单失败:", error);
      throw error;
    }
  };

  // 批量撤单
  const cancelAllOrders = async (symbol?: string) => {
    const orders = symbol
      ? store.getters["trade/getPendingOrdersBySymbol"](symbol)
      : store.state.trade.pendingOrders;

    const results = await Promise.allSettled(
      orders.map((order: any) => cancelOrder(order.order_id)),
    );

    const successCount = results.filter(
      (r: any) => r.status === "fulfilled",
    ).length;
    const failedCount = results.filter(
      (r: any) => r.status === "rejected",
    ).length;

    return { successCount, failedCount };
  };

  // 验证订单
  const validateOrder = async (order: any) => {
    const errors: string[] = [];

    // 基本验证
    if (!order.ts_code) errors.push("股票代码不能为空");
    if (!order.volume || order.volume <= 0) errors.push("数量必须大于0");
    if (order.order_type === "limit" && (!order.price || order.price <= 0)) {
      errors.push("限价单必须指定有效价格");
    }

    // 资金验证
    if (order.direction === "buy") {
      const availableCash = store.getters["trade/getAvailableCash"];
      const estimatedCost =
        order.volume *
        (order.price || store.getters["market/getCurrentPrice"](order.ts_code));

      if (estimatedCost > availableCash) {
        errors.push("可用资金不足");
      }
    }

    // 持仓验证
    if (order.direction === "sell") {
      const position = store.getters["trade/getPosition"](order.ts_code);
      if (!position || position.available_volume < order.volume) {
        errors.push("可用持仓不足");
      }
    }

    // 交易时间验证
    if (!isTradingTime()) {
      errors.push("当前不在交易时间内");
    }

    if (errors.length > 0) {
      throw new Error(errors.join("; "));
    }
  };

  // 检查交易时间
  const isTradingTime = () => {
    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();
    const time = hour * 100 + minute;

    // A股交易时间: 9:30-11:30, 13:00-15:00
    const isMorning = time >= 930 && time <= 1130;
    const isAfternoon = time >= 1300 && time <= 1500;
    const isWeekend = now.getDay() === 0 || now.getDay() === 6;

    return !isWeekend && (isMorning || isAfternoon);
  };

  // 生成订单ID
  const generateOrderId = () => {
    const timestamp = Date.now().toString();
    const random = Math.random().toString(36).substr(2, 9);
    return `order_${timestamp}_${random}`;
  };

  // 获取交易费用估算
  const estimateFees = (
    price: number,
    volume: number,
    direction: "buy" | "sell",
  ) => {
    const amount = price * volume;

    // 佣金: 万一免五
    const commission = amount * 0.0001;

    // 印花税: 卖出时 0.05%（2023-08-28 起）
    const tax = direction === "sell" ? amount * 0.0005 : 0;

    // 过户费: 万0.1（沪深两市、买卖双向）
    const transferFee = amount * 0.0001;

    return {
      commission,
      tax,
      transferFee,
      total: commission + tax + transferFee,
      netAmount:
        direction === "buy"
          ? amount + commission + transferFee
          : amount - commission - tax - transferFee,
    };
  };

  return {
    isTrading,
    pendingOrders,
    quickOrder,
    marketOrder,
    limitOrder,
    cancelOrder,
    cancelAllOrders,
    estimateFees,
    isTradingTime,
  };
}
