<!--日期选择器-->
<script setup lang="ts">
import { ref, computed } from "vue";
import { NDatePicker, NButton } from "naive-ui";

const props = withDefaults(
  defineProps<{
    minDate?: string;
    maxDate?: string;
    initialStartDate?: string;
    initialEndDate?: string;
  }>(),
  {
    minDate: "2010-01-01",
    maxDate: () => new Date().toISOString().split("T")[0],
  },
);

const emit = defineEmits<{
  dateChange: [payload: { start: string; end: string; tradingDays: number }];
}>();

const dateRange = ref<[string, string]>([
  props.initialStartDate || "2020-01-01",
  props.initialEndDate || new Date().toISOString().split("T")[0],
]);

const quickPeriods = [
  { label: "最近1年", value: 1 },
  { label: "最近3年", value: 3 },
  { label: "最近5年", value: 5 },
  { label: "全部数据", value: "all" as const },
];

const formattedStartDate = computed(() => formatDate(dateRange.value[0]));
const formattedEndDate = computed(() => formatDate(dateRange.value[1]));

const tradingDays = computed(() => {
  const [start, end] = dateRange.value;
  if (!start || !end) return 0;
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  const diffDays = Math.ceil(Math.abs(endMs - startMs) / (1000 * 60 * 60 * 24));
  return Math.round((diffDays / 365) * 252);
});

const isDateDisabled = (ts: number) => {
  const minTs = new Date(props.minDate).getTime();
  const maxTs = new Date(props.maxDate).getTime();
  return ts < minTs || ts > maxTs;
};

const formatDate = (dateString: string) => {
  if (!dateString) return "未选择";
  const date = new Date(dateString);
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
};

const selectPeriod = (years: number | "all") => {
  const end = new Date();
  const start = new Date();
  if (years === "all") {
    dateRange.value = [props.minDate, props.maxDate];
  } else {
    start.setFullYear(end.getFullYear() - years);
    dateRange.value = [
      start.toISOString().split("T")[0],
      end.toISOString().split("T")[0],
    ];
  }
  emitDateChange();
};

const handleDateChange = () => {
  emitDateChange();
};

const emitDateChange = () => {
  emit("dateChange", {
    start: dateRange.value[0],
    end: dateRange.value[1],
    tradingDays: tradingDays.value,
  });
};
</script>

<template>
  <div class="date-range-picker">
    <div class="date-input-group">
      <n-date-picker
        v-model:formatted-value="dateRange"
        type="daterange"
        value-format="yyyy-MM-dd"
        :is-date-disabled="isDateDisabled"
        clearable
        @update:formatted-value="handleDateChange"
      />
    </div>

    <div class="preview">
      <p>
        回测时间范围：<span
          >{{ formattedStartDate }} 至 {{ formattedEndDate }}</span
        >
      </p>
      <p>
        总交易日数：<span>{{ tradingDays }}</span> 天
      </p>
    </div>

    <div class="quick-selection">
      <n-button
        v-for="period in quickPeriods"
        :key="period.label"
        size="small"
        @click="selectPeriod(period.value)"
      >
        {{ period.label }}
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.date-range-picker {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.date-input-group {
  margin-bottom: 20px;
}

.preview {
  padding: 15px;
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  font-size: 0.95rem;
  margin-bottom: 20px;
}

.preview p {
  margin-bottom: 8px;
}

.preview span {
  color: #64b5f6;
  font-weight: 500;
}

.quick-selection {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
