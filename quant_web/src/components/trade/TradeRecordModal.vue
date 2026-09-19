<template>
  <NModal
    v-model:show="visible"
    preset="card"
    title="录入成交"
    style="width: 520px"
    :mask-closable="false"
    @close="resetForm"
  >
    <NForm
      ref="formRef"
      :model="form"
      :rules="rules"
      label-placement="left"
      label-width="80px"
      @keyup.enter="handleSubmit"
    >
      <NFormItem label="股票代码" path="ts_code">
        <NInput
          v-model:value="form.ts_code"
          placeholder="如 000001.SZ"
          :input-props="{ style: 'text-transform: uppercase' }"
        />
      </NFormItem>

      <NFormItem label="交易方向" path="direction">
        <NRadioGroup v-model:value="form.direction">
          <NRadioButton value="buy">买入</NRadioButton>
          <NRadioButton value="sell">卖出</NRadioButton>
        </NRadioGroup>
      </NFormItem>

      <NFormItem label="成交价格" path="price">
        <NInputNumber
          v-model:value="form.price"
          :decimal-places="2"
          :step="0.01"
          :min="0.01"
        />
      </NFormItem>

      <NFormItem label="成交数量" path="quantity">
        <NInputNumber
          v-model:value="form.quantity"
          :min="100"
          :step="100"
        />
        <span class="unit-hint">股（A股最小100股）</span>
      </NFormItem>

      <NFormItem label="成交日期" path="trade_date">
        <NDatePicker
          v-model:formatted-value="form.trade_date"
          type="date"
          value-format="yyyy-MM-dd"
          :is-date-disabled="dateDisabled"
        />
      </NFormItem>

      <NDivider>费用（选填，不填则自动计算）</NDivider>

      <NFormItem label="佣金">
        <NInputNumber
          v-model:value="form.fees.commission"
          :decimal-places="2"
          :min="0"
          placeholder="自动计算"
        />
      </NFormItem>

      <NFormItem label="印花税">
        <NInputNumber
          v-model:value="form.fees.stamp_duty"
          :decimal-places="2"
          :min="0"
          placeholder="卖出时自动计算"
        />
      </NFormItem>

      <NFormItem label="过户费">
        <NInputNumber
          v-model:value="form.fees.transfer_fee"
          :decimal-places="2"
          :min="0"
          placeholder="沪市自动计算"
        />
      </NFormItem>

      <NDivider />

      <NFormItem label="关联信号">
        <NInput
          v-model:value="form.signal_id"
          placeholder="可选，信号ID"
        />
      </NFormItem>

      <!-- 记账去向反显（2026-09-17）：
           手动录单按 (account_id, ts_code, strategy_id) 三维定位，此前不反显这两维 →
           用户看不到会记到哪个账户/策略，账户错位时只在提交后被拒（512400.SH 事故）。 -->
      <NFormItem label="记账去向">
        <div class="target-box">
          <template v-if="target.accountId || target.strategyId">
            <div class="target-row">
              <span class="target-key">账户</span>
              <span class="target-val">
                {{
                  target.accountName ||
                  (target.accountId ? "—" : "由该策略绑定的账户决定")
                }}
              </span>
            </div>
            <div class="target-row">
              <span class="target-key">策略</span>
              <span class="target-val">
                {{
                  target.strategyName ||
                  (target.strategyId ? "（未命名策略）" : "手工持仓（无策略）")
                }}
              </span>
            </div>
            <div class="target-ids">
              <span v-if="target.accountId">{{ target.accountId }}</span>
              <span v-if="target.accountId && target.strategyId"> · </span>
              <span v-if="target.strategyId">{{ target.strategyId }}</span>
            </div>
          </template>
          <span v-else class="target-hint">
            未指定 —— 提交时按该票持仓自动定位账户与策略
          </span>
        </div>
      </NFormItem>

      <NFormItem label="关联策略">
        <div class="strategy-row">
          <template v-if="resolvedStrategyId && !manualStrategy">
            <span class="target-val">
              {{ resolvedStrategyName || resolvedStrategyId }}
            </span>
            <NButton text type="primary" size="tiny" @click="manualStrategy = true">
              改为手动指定
            </NButton>
          </template>
          <template v-else>
            <NInput
              v-model:value="form.strategy_id"
              placeholder="留空则按该票持仓自动定位"
            />
            <NButton
              v-if="target.strategyId"
              text
              size="tiny"
              @click="cancelManualStrategy"
            >
              取消手动指定
            </NButton>
          </template>
        </div>
      </NFormItem>

      <!-- 预估 -->
      <div v-if="previewInfo" class="preview-box">
        <div class="preview-row">
          <span>成交金额</span>
          <span>¥{{ previewInfo.tradeAmount.toLocaleString() }}</span>
        </div>
        <div class="preview-row">
          <span>预估费用</span>
          <span>¥{{ previewInfo.estFees.toFixed(2) }}</span>
        </div>
        <div class="preview-row total">
          <span>{{ form.direction === "buy" ? "预估支出" : "预估收入" }}</span>
          <span>¥{{ previewInfo.netAmount.toLocaleString() }}</span>
        </div>
      </div>
    </NForm>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="visible = false">取消</NButton>
        <NButton type="primary" :loading="submitting" @click="handleSubmit">
          确认录入
        </NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from "vue";
import {
  NModal,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NRadioGroup,
  NRadioButton,
  NDatePicker,
  NDivider,
  NButton,
  NSpace,
  useMessage,
} from "naive-ui";
import type { FormInst, FormRules } from "naive-ui";
import tradeAPI from "@/api/trade";

const props = defineProps<{
  modelValue: boolean;
  prefilled?: {
    signal_id?: string;
    strategy_id?: string;
    ts_code?: string;
    direction?: string;
    price?: number;
    quantity?: number;
    // 2026-09-17 新增：记账去向反显（account_name/strategy_name 仅用于展示）
    account_id?: string;
    account_name?: string;
    strategy_name?: string;
  } | null;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "submitted"): void;
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const submitting = ref(false);

const form = reactive({
  ts_code: "",
  direction: "buy" as string,
  price: null as number | null,
  quantity: null as number | null,
  trade_date: new Date().toISOString().slice(0, 10),
  signal_id: "",
  strategy_id: "",
  fees: {
    commission: null as number | null,
    stamp_duty: null as number | null,
    transfer_fee: null as number | null,
  },
});

// ---- 记账去向反显（2026-09-17）----
// 仅用于"提交前告知用户会记到哪个账户/策略"：account_id 不随请求发送（后端按
// ts_code 自行解析），strategy_id 会发送 —— 故标的被改动后必须一并清掉预填的
// 策略，否则会把成交记到上一个标的的策略维度上。
const target = reactive({
  accountId: "",
  accountName: "",
  strategyId: "",
  strategyName: "",
  fromPrefill: false,
  prefilledCode: "",
});
const manualStrategy = ref(false);

const resolvedStrategyId = computed(
  () => form.strategy_id || target.strategyId || "",
);
const resolvedStrategyName = computed(() => {
  if (!form.strategy_id) return target.strategyName;
  return form.strategy_id === target.strategyId ? target.strategyName : "";
});

function resetTarget() {
  // 预填的策略随标的变更失效（手工填写的 strategy_id 不在此列）
  if (form.strategy_id && form.strategy_id === target.strategyId) {
    form.strategy_id = "";
  }
  target.accountId = "";
  target.accountName = "";
  target.strategyId = "";
  target.strategyName = "";
  target.fromPrefill = false;
  target.prefilledCode = "";
  manualStrategy.value = false;
}

function cancelManualStrategy() {
  form.strategy_id = "";
  manualStrategy.value = false;
}

watch(
  () => form.ts_code,
  (code) => {
    if (target.fromPrefill && code !== target.prefilledCode) {
      resetTarget();
    }
  },
);

const rules: FormRules = {
  ts_code: { required: true, message: "请输入股票代码", trigger: "blur" },
  direction: { required: true, message: "请选择交易方向" },
  price: {
    required: true,
    type: "number",
    min: 0.01,
    message: "请输入有效价格",
    trigger: "blur",
  },
  quantity: {
    required: true,
    type: "number",
    min: 100,
    message: "请输入有效数量（≥100股）",
    trigger: "blur",
  },
};

const previewInfo = computed(() => {
  if (!form.price || !form.quantity) return null;
  const tradeAmount = form.price * form.quantity;
  // 简单预估：佣金万一免五、卖出印花税 0.05%、过户费万0.1（沪深双边）
  let commission = form.fees.commission ?? tradeAmount * 0.0001;
  let stamp = form.fees.stamp_duty ?? (form.direction === "sell" ? tradeAmount * 0.0005 : 0);
  let transfer = form.fees.transfer_fee ?? tradeAmount * 0.0001;
  const estFees = commission + stamp + transfer;
  const netAmount = form.direction === "buy" ? tradeAmount + estFees : tradeAmount - estFees;
  return { tradeAmount, estFees, netAmount };
});

function dateDisabled(ts: number) {
  return ts > Date.now();
}

async function handleSubmit() {
  const inst = formRef.value;
  if (!inst) return;
  try {
    await inst.validate();
  } catch {
    return;
  }
  if (!form.price || !form.quantity) return;

  submitting.value = true;
  try {
    // 未填的费用项置 null，由后端按统一费率自动计算（只填佣金时印花税/过户费仍自动算）
    const feesPayload: any = {
      commission: form.fees.commission ?? null,
      stamp_duty: form.fees.stamp_duty ?? null,
      transfer_fee: form.fees.transfer_fee ?? null,
    };

    const resp: any = await tradeAPI.recordTrade({
      ts_code: form.ts_code,
      direction: form.direction,
      price: form.price,
      quantity: form.quantity,
      trade_date: form.trade_date,
      signal_id: form.signal_id || undefined,
      strategy_id: form.strategy_id || undefined,
      fees: feesPayload,
    });

    // 反显后端实际解析出的记账去向，避免"记了但不知道记到哪个账户/策略"
    const _d = resp?.data || {};
    const _where = [_d.account_name, _d.strategy_name].filter(Boolean).join(" / ");
    message.success(_where ? `录入成功：记账到 ${_where}` : "成交录入成功");
    visible.value = false;
    emit("submitted");
    resetForm();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "录入失败");
  } finally {
    submitting.value = false;
  }
}

function resetForm() {
  resetTarget();
  form.ts_code = "";
  form.direction = "buy";
  form.price = null;
  form.quantity = null;
  form.trade_date = new Date().toISOString().slice(0, 10);
  form.signal_id = "";
  form.strategy_id = "";
  form.fees.commission = null;
  form.fees.stamp_duty = null;
  form.fees.transfer_fee = null;
}

// 预填数据（从信号 / 持仓 / 订单行点击进入时）
watch(
  () => props.prefilled,
  (val) => {
    resetTarget();
    if (val) {
      if (val.ts_code) form.ts_code = val.ts_code;
      if (val.direction) form.direction = val.direction;
      if (val.price) form.price = val.price;
      if (val.quantity) form.quantity = val.quantity;
      if (val.signal_id) form.signal_id = val.signal_id;
      if (val.strategy_id) form.strategy_id = val.strategy_id;
      // 记账去向反显：账户/策略名缺失时退化为展示 ID（用户至少能看到记到哪）
      if (val.account_id || val.strategy_id) {
        target.accountId = val.account_id || "";
        target.accountName = val.account_name || "";
        target.strategyId = val.strategy_id || "";
        target.strategyName = val.strategy_name || "";
        target.fromPrefill = true;
        target.prefilledCode = val.ts_code || "";
      }
    }
    // 每次打开都重置费用字段
    form.fees.commission = null;
    form.fees.stamp_duty = null;
    form.fees.transfer_fee = null;
  },
  { immediate: true },
);
</script>

<style scoped lang="scss">
.unit-hint {
  margin-left: 8px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

// ---- 记账去向反显（2026-09-17）----
.target-box {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--n-border-radius);
  border: 1px solid var(--n-border-color);
  background: var(--n-card-color);
  line-height: 1.7;
}

.target-row {
  display: flex;
  gap: 8px;
}

.target-key {
  flex: none;
  font-size: 13px;
  color: var(--n-text-color-3);
}

.target-val {
  font-size: 13px;
  color: var(--n-text-color-1);
}

.target-ids {
  margin-top: 2px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  color: var(--n-text-color-3);
  word-break: break-all;
}

.target-hint {
  font-size: 13px;
  color: var(--n-text-color-3);
}

.strategy-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;

  :deep(.n-input) {
    flex: 1;
  }
}

.preview-box {
  margin-top: 8px;
  padding: 12px 16px;
  border-radius: var(--n-border-radius);
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);

  .preview-row {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    line-height: 1.8;
    color: var(--n-text-color-2);

    &.total {
      margin-top: 4px;
      padding-top: 8px;
      border-top: 1px solid var(--n-border-color);
      font-weight: 600;
      font-size: 14px;
      color: var(--n-text-color-1);
    }
  }
}
</style>
