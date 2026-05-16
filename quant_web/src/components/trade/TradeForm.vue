<template>
  <NModal
    v-model:show="visible"
    preset="card"
    :title="`交易确认 - ${currentSignal.symbol} ${currentSignal.name}`"
    style="width: 500px"
    @close="resetForm"
  >
    <NForm
      ref="tradeFormRef"
      :model="form"
      :rules="rules"
      label-placement="left"
      label-width="80px"
    >
      <NFormItem label="交易方向">
        <NRadioGroup v-model:value="form.direction">
          <NRadioButton value="BUY">买入</NRadioButton>
          <NRadioButton value="SELL">卖出</NRadioButton>
        </NRadioGroup>
      </NFormItem>

      <NFormItem label="价格类型">
        <NRadioGroup v-model:value="form.priceType">
          <NRadioButton value="LIMIT">限价</NRadioButton>
          <NRadioButton value="MARKET">市价</NRadioButton>
        </NRadioGroup>
      </NFormItem>

      <NFormItem
        v-if="form.priceType === 'LIMIT'"
        label="委托价格"
        path="price"
      >
        <NInputNumber
          v-model:value="form.price"
          :decimal-places="2"
          :step="0.01"
          :min="0.01"
        />
        <span class="price-tips">
          最新价: {{ currentSignal.lastPrice }}
          <span :class="currentSignal.change >= 0 ? 'up' : 'down'">
            ({{ currentSignal.change >= 0 ? "+" : ""
            }}{{ currentSignal.change }}%)
          </span>
        </span>
      </NFormItem>

      <NFormItem label="委托数量" path="quantity">
        <NInputNumber v-model:value="form.quantity" :min="100" :step="100" />
        <span class="quantity-tips">
          可{{ form.direction === "BUY" ? "买" : "卖" }}:
          {{
            form.direction === "BUY"
              ? availableCash
              : currentSignal.availableShares
          }}股
        </span>
      </NFormItem>

      <NFormItem label="总金额">
        <span class="total-amount">
          {{
            (form.price * form.quantity).toLocaleString("zh-CN", {
              style: "currency",
              currency: "CNY",
              minimumFractionDigits: 2,
            })
          }}
        </span>
      </NFormItem>

      <NFormItem label="交易账户" path="account">
        <NSelect
          v-model:value="form.account"
          :options="accountOptions"
          placeholder="选择交易账户"
        />
      </NFormItem>
    </NForm>

    <template #footer>
      <div class="dialog-footer">
        <NButton @click="visible = false">取消</NButton>
        <NButton type="primary" :loading="submitting" @click="submitForm"
          >确定</NButton
        >
      </div>
    </template>
  </NModal>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from "vue";
import {
  NModal,
  NForm,
  NFormItem,
  NRadioGroup,
  NRadioButton,
  NInputNumber,
  NSelect,
  NButton,
} from "naive-ui";
import type { FormRules, FormInst } from "naive-ui";

interface Signal {
  symbol: string;
  name: string;
  lastPrice: number;
  change: number;
  availableShares: number;
  recommendation: string;
}

interface Account {
  id: string;
  name: string;
  broker: string;
}

const props = withDefaults(
  defineProps<{
    signal?: Signal | null;
    accounts?: Account[];
  }>(),
  {
    signal: null,
    accounts: () => [],
  },
);

const emit = defineEmits<{
  submit: [data: any];
}>();

const visible = ref(false);
const tradeFormRef = ref<FormInst | null>(null);
const submitting = ref(false);
const availableCash = ref(100000);

const currentSignal = ref<Signal>({
  symbol: "",
  name: "",
  lastPrice: 0,
  change: 0,
  availableShares: 0,
  recommendation: "BUY",
});

const form = reactive({
  direction: "BUY",
  priceType: "LIMIT",
  price: 0,
  quantity: 100,
  account: "",
});

const accountOptions = computed(() =>
  props.accounts.map((acc) => ({
    label: `${acc.name} (${acc.broker})`,
    value: acc.id,
  })),
);

const rules: FormRules = {
  price: [
    { required: true, message: "请输入委托价格", trigger: "blur" },
    { type: "number", min: 0.01, message: "价格必须大于0", trigger: "blur" },
  ],
  quantity: [
    { required: true, message: "请输入委托数量", trigger: "blur" },
    { type: "number", min: 100, message: "最小交易100股", trigger: "blur" },
  ],
  account: [{ required: true, message: "请选择交易账户", trigger: "change" }],
};

watch(
  () => props.signal,
  (newVal) => {
    if (newVal && newVal.symbol) {
      currentSignal.value = {
        symbol: newVal.symbol || "",
        name: newVal.name || "",
        lastPrice: newVal.lastPrice || 0,
        change: newVal.change || 0,
        availableShares: newVal.availableShares || 0,
        recommendation: newVal.recommendation || "BUY",
      };
      form.price = newVal.lastPrice;
      form.direction = newVal.recommendation === "BUY" ? "BUY" : "SELL";
      visible.value = true;
    }
  },
);

const resetForm = () => {
  tradeFormRef.value?.restoreValidation();
  form.price = 0;
  form.quantity = 100;
  currentSignal.value = {
    symbol: "",
    name: "",
    lastPrice: 0,
    change: 0,
    availableShares: 0,
    recommendation: "BUY",
  };
};

const submitForm = () => {
  tradeFormRef.value?.validate((errors) => {
    if (!errors) {
      submitting.value = true;
      setTimeout(() => {
        emit("submit", {
          ...form,
          symbol: currentSignal.value.symbol,
          name: currentSignal.value.name,
        });
        submitting.value = false;
        visible.value = false;
      }, 800);
    }
  });
};
</script>

<style scoped>
.price-tips,
.quantity-tips {
  margin-left: 10px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.total-amount {
  font-size: 18px;
  font-weight: bold;
  color: #f56c6c;
}

.up {
  color: #f56c6c;
}
.down {
  color: #5cb87a;
}

.dialog-footer {
  text-align: right;
}
</style>
