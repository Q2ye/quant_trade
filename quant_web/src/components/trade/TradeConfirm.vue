<!--交易确认弹窗-->
<script setup lang="ts">
import { NModal, NButton, NSpace } from "naive-ui";
import { Icon } from "@iconify/vue";
import { useMessage } from "naive-ui";

const props = defineProps<{
  visible: boolean;
  order: {
    direction: string;
    symbol: string;
    name: string;
    type: string;
    price: number;
    quantity: number;
    triggerPrice?: number;
    amount: number;
  };
}>();

const emit = defineEmits<{
  cancel: [];
  confirm: [order: typeof props.order];
}>();

const message = useMessage();

const isBuy = props.order.direction === "买入";
const accountBalance = 1250680.5;

const cancel = () => emit("cancel");
const confirm = () => {
  emit("confirm", props.order);
  message.success("交易指令已发送");
};
</script>

<template>
  <n-modal
    :show="visible"
    preset="card"
    :on-close="cancel"
    title="交易确认"
    style="max-width: 500px"
  >
    <div class="trade-summary">
      <div class="summary-item">
        <span class="label">交易方向:</span>
        <span class="value" :class="isBuy ? 'buy' : 'sell'">
          {{ order.direction }}
        </span>
      </div>
      <div class="summary-item">
        <span class="label">证券代码:</span>
        <span class="value">{{ order.symbol }}</span>
      </div>
      <div class="summary-item">
        <span class="label">证券名称:</span>
        <span class="value">{{ order.name }}</span>
      </div>
      <div class="summary-item">
        <span class="label">订单类型:</span>
        <span class="value">{{ order.type }}</span>
      </div>
      <div class="summary-item">
        <span class="label">价格:</span>
        <span class="value">{{ order.price }}</span>
      </div>
      <div class="summary-item">
        <span class="label">数量:</span>
        <span class="value">{{ order.quantity }}</span>
      </div>
      <div v-if="order.triggerPrice" class="summary-item">
        <span class="label">触发价格:</span>
        <span class="value">{{ order.triggerPrice }}</span>
      </div>
      <div class="summary-item highlight">
        <span class="label">交易金额:</span>
        <span class="value">¥{{ order.amount.toLocaleString() }}</span>
      </div>
    </div>

    <div class="account-info">
      <div class="info-item">
        <span class="label">可用资金:</span>
        <span class="value">¥{{ accountBalance.toLocaleString() }}</span>
      </div>
      <div class="info-item">
        <span class="label">交易后资金:</span>
        <span
          class="value"
          :class="isBuy ? 'negative' : 'positive'"
        >
          {{
            isBuy
              ? "¥" + (accountBalance - order.amount).toLocaleString()
              : "¥" + (accountBalance + order.amount).toLocaleString()
          }}
        </span>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button @click="cancel">
          <template #icon><Icon icon="ant-design:close-outlined" /></template>
          取消
        </n-button>
        <n-button type="success" @click="confirm">
          <template #icon><Icon icon="ant-design:check-outlined" /></template>
          确认交易
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.trade-summary {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.summary-item {
  display: flex;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(64, 158, 255, 0.1);
}

.summary-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.summary-item.highlight {
  padding-top: 10px;
  margin-top: 10px;
  border-top: 1px solid rgba(64, 158, 255, 0.3);
}

.label {
  width: 100px;
  color: #a8c7ff;
  font-size: 0.95rem;
}

.value {
  flex: 1;
  font-weight: 500;
  color: #e0e7ff;
}

.value.buy { color: #5cdd8b; }
.value.sell { color: #ff6b6b; }

.highlight .value {
  font-size: 1.2rem;
  font-weight: 700;
  color: #64b5f6;
}

.account-info {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.info-item {
  display: flex;
  margin-bottom: 10px;
}

.info-item:last-child { margin-bottom: 0; }

.info-item .value.positive { color: #5cdd8b; }
.info-item .value.negative { color: #ff6b6b; }
</style>
