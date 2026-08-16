<script setup lang="ts">
// 仓位建议卡（v5）—— 温度 → 4 带仓位规则表（纯前端）+ 全带对照图例（填充卡内空间）
import { computed } from "vue";
import { NEmpty } from "naive-ui";

const props = defineProps<{ temperature: number | null }>();

interface ZoneInfo {
  zone: string;
  short: string;
  icon: string;
  range: string;
  color: string;
  text: string;
}

const ZONES: ZoneInfo[] = [
  {
    zone: "低温布局区",
    short: "低温",
    icon: "❄",
    range: "60~80%",
    color: "#26a69a",
    text: "估值便宜 + 情绪冰点，适合分批布局宽基/行业 ETF",
  },
  {
    zone: "温和进攻区",
    short: "温和",
    icon: "🌤",
    range: "40~60%",
    color: "#ff9800",
    text: "状态健康，持仓为主，回调加仓",
  },
  {
    zone: "中性观察区",
    short: "中性",
    icon: "⚖",
    range: "20~40%",
    color: "#ffb74d",
    text: "估值情绪偏高，降低仓位，保留底仓",
  },
  {
    zone: "高温防守区",
    short: "高温",
    icon: "🔥",
    range: "0~20%",
    color: "#ef5350",
    text: "过热拥挤，防守为主，等待降温",
  },
];

function zoneOf(t: number): ZoneInfo {
  if (t < 30) return ZONES[0];
  if (t < 50) return ZONES[1];
  if (t <= 70) return ZONES[2];
  return ZONES[3];
}

const advice = computed(() =>
  props.temperature == null ? null : zoneOf(props.temperature),
);
const rangeStart = computed(() =>
  advice.value ? parseInt(advice.value.range.split("~")[0]) : 0,
);
const rangeEnd = computed(() =>
  advice.value ? parseInt(advice.value.range.split("~")[1]) : 0,
);
</script>

<template>
  <n-card size="small" class="full-height-card advice-card" title="仓位建议">
    <template v-if="advice">
      <div class="advice-zone">
        <span class="advice-icon">{{ advice.icon }}</span>
        <span class="advice-name" :style="{ color: advice.color }">{{ advice.zone }}</span>
      </div>
      <div class="advice-temp">
        {{ temperature != null ? temperature.toFixed(1) : "--" }}<span class="advice-unit">℃</span>
      </div>
      <div class="advice-range">建议仓位 {{ advice.range }}</div>
      <div class="advice-bar">
        <div class="advice-bar-low" :style="{ flex: rangeStart }" />
        <div
          class="advice-bar-mid"
          :style="{ flex: rangeEnd - rangeStart, background: advice.color }"
        />
        <div class="advice-bar-high" :style="{ flex: 100 - rangeEnd }" />
      </div>
      <div class="advice-text">{{ advice.text }}</div>
      <div class="advice-zones">
        <div
          v-for="z in ZONES"
          :key="z.zone"
          class="zone-row"
          :class="{ active: advice.zone === z.zone }"
        >
          <span class="zone-icon">{{ z.icon }}</span>
          <span class="zone-name">{{ z.short }}</span>
          <span class="zone-range">{{ z.range }}</span>
        </div>
      </div>
    </template>
    <n-empty v-else description="温度计数据不足" size="small" style="padding: 24px" />
    <div class="advice-note">温度计为系统量化指标，不构成投资建议</div>
  </n-card>
</template>

<style lang="scss" scoped>
.full-height-card {
  height: 100%;
}
.advice-card {
  :deep(.n-card__content) {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
  }
}
.advice-zone {
  display: flex;
  align-items: center;
  gap: 6px;
}
.advice-icon {
  font-size: 18px;
}
.advice-name {
  font-size: 15px;
  font-weight: 700;
}
.advice-temp {
  font-size: 30px;
  font-weight: 700;
  font-family: monospace;
  line-height: 1;
}
.advice-unit {
  font-size: 13px;
  color: var(--n-text-color-3);
  margin-left: 2px;
}
.advice-range {
  font-size: 13px;
  font-weight: 600;
}
.advice-bar {
  display: flex;
  width: 100%;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  .advice-bar-low {
    background: rgba(255, 255, 255, 0.06);
  }
  .advice-bar-mid {
    border-radius: 2px;
  }
  .advice-bar-high {
    background: rgba(255, 255, 255, 0.06);
  }
}
.advice-text {
  font-size: 11px;
  color: var(--n-text-color-2);
  text-align: center;
  line-height: 1.4;
}
.advice-zones {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 6px;
  .zone-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    opacity: 0.55;
    &.active {
      opacity: 1;
      background: rgba(255, 255, 255, 0.06);
    }
    .zone-icon {
      width: 18px;
      text-align: center;
    }
    .zone-name {
      color: var(--n-text-color-2);
    }
    .zone-range {
      margin-left: auto;
      color: var(--n-text-color-3);
      font-family: monospace;
    }
  }
}
.advice-note {
  font-size: 10px;
  color: var(--n-text-color-3);
  text-align: center;
  margin-top: auto;
  padding-top: 8px;
}
</style>
