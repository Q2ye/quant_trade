<script setup lang="ts">
import { computed } from "vue";
import { NSelect, NStatistic } from "naive-ui";
import type { Account } from "@/types";

const props = defineProps<{
  accounts: Account[];
  selectedAccountId: string | null;
  dailyPnl?: number;
  dailyPnlRatio?: number;
}>();

const emit = defineEmits<{
  (e: "select-account", id: string): void;
}>();

const accountOptions = computed(() =>
  props.accounts.map((a) => ({
    label: `${a.account_name || a.account_number} (${a.broker})`,
    value: String(a.id),
  })),
);

const selectedAccount = computed(
  () =>
    props.accounts.find((a) => String(a.id) === props.selectedAccountId) ??
    props.accounts[0],
);

const pnlColor = computed(() =>
  (props.dailyPnl ?? 0) >= 0
    ? "var(--color-stock-up)"
    : "var(--color-stock-down)",
);
</script>

<template>
  <div class="account-bar">
    <div class="account-bar-left">
      <n-select
        :value="selectedAccountId"
        :options="accountOptions"
        size="small"
        class="account-switcher"
        placeholder="选择账户"
        @update:value="(v: string) => emit('select-account', v)"
      />
    </div>
    <div class="account-bar-stats">
      <div class="stat-block">
        <span class="stat-label">总资产</span>
        <span class="stat-value"
          >¥{{ selectedAccount?.total_asset?.toLocaleString() ?? "--" }}</span
        >
      </div>
      <div class="stat-divider" />
      <div class="stat-block">
        <span class="stat-label">可用</span>
        <span class="stat-value"
          >¥{{
            selectedAccount?.available_cash?.toLocaleString() ?? "--"
          }}</span
        >
      </div>
      <div class="stat-divider" />
      <div class="stat-block">
        <span class="stat-label">市值</span>
        <span class="stat-value"
          >¥{{ selectedAccount?.market_value?.toLocaleString() ?? "--" }}</span
        >
      </div>
      <div class="stat-divider" />
      <div class="stat-block">
        <span class="stat-label">当日盈亏</span>
        <span class="stat-value" :style="{ color: pnlColor }">
          {{ (dailyPnl ?? 0) >= 0 ? "+" : "" }}¥{{
            (dailyPnl ?? 0).toLocaleString()
          }}
        </span>
        <span
          v-if="dailyPnlRatio != null"
          class="stat-sub"
          :style="{ color: pnlColor }"
        >
          ({{ (dailyPnlRatio >= 0 ? "+" : "") + dailyPnlRatio.toFixed(2) }}%)
        </span>
      </div>
    </div>
    <div class="account-bar-right">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.account-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(68, 138, 255, 0.06);
  border: 1px solid rgba(68, 138, 255, 0.1);
  border-radius: 6px;
  margin-bottom: 16px;
  gap: 16px;
  flex-shrink: 0;
}

.account-bar-left {
  flex-shrink: 0;
}

.account-switcher {
  width: 200px;
}

.account-bar-stats {
  display: flex;
  align-items: center;
  gap: 0;
  flex: 1;
  justify-content: center;
}

.stat-block {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
}

.stat-divider {
  width: 1px;
  height: 28px;
  background: rgba(255, 255, 255, 0.08);
}

.stat-label {
  font-size: 11px;
  color: var(--n-text-color-3);
  text-transform: uppercase;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
}

.stat-sub {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.account-bar-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
