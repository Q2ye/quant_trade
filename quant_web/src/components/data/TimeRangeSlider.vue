<!--时间范围滑块-->
<script setup lang="ts">
import { ref, computed, watch } from "vue";
import dayjs from "dayjs";

const props = withDefaults(
  defineProps<{
    minDate?: string | Date;
    maxDate?: string | Date;
    value?: Date[];
  }>(),
  {
    minDate: () => dayjs().subtract(5, "year").toDate(),
    maxDate: () => new Date(),
    value: () => [dayjs().subtract(1, "year").toDate(), new Date()],
  },
);

const emit = defineEmits<{
  input: [value: Date[]];
  change: [value: Date[]];
}>();

const localValue = ref<Date[]>([...props.value]);
const dateFormat = "YYYY-MM-DD";

const minTimestamp = computed(() => new Date(props.minDate).getTime());
const maxTimestamp = computed(() => new Date(props.maxDate).getTime());

const range = computed(() => maxTimestamp.value - minTimestamp.value);

const startPercent = computed(
  () =>
    ((localValue.value[0].getTime() - minTimestamp.value) / range.value) * 100,
);

const endPercent = computed(
  () =>
    100 -
    ((maxTimestamp.value - localValue.value[1].getTime()) / range.value) * 100,
);

watch(
  () => props.value,
  (newVal) => {
    localValue.value = [...newVal];
  },
);

const formatDate = (date: Date) => dayjs(date).format(dateFormat);

const emitChange = () => {
  emit("input", [...localValue.value]);
  emit("change", [...localValue.value]);
};

const handleStartChange = (e: Event) => {
  const timestamp = parseInt((e.target as HTMLInputElement).value);
  const newDate = new Date(timestamp);
  if (newDate < localValue.value[1]) {
    localValue.value[0] = newDate;
    emitChange();
  }
};

const handleEndChange = (e: Event) => {
  const timestamp = parseInt((e.target as HTMLInputElement).value);
  const newDate = new Date(timestamp);
  if (newDate > localValue.value[0]) {
    localValue.value[1] = newDate;
    emitChange();
  }
};
</script>

<template>
  <div class="time-range-slider">
    <div class="date-display">
      <span>{{ formatDate(localValue[0]) }}</span>
      <span>至</span>
      <span>{{ formatDate(localValue[1]) }}</span>
    </div>

    <div class="slider-container">
      <div class="slider-track">
        <div
          class="slider-range"
          :style="{
            left: `${startPercent}%`,
            right: `${100 - endPercent}%`,
          }"
        />
      </div>

      <input
        type="range"
        class="slider-handle start-handle"
        :min="minTimestamp"
        :max="maxTimestamp"
        :value="localValue[0].getTime()"
        @input="handleStartChange"
      />

      <input
        type="range"
        class="slider-handle end-handle"
        :min="minTimestamp"
        :max="maxTimestamp"
        :value="localValue[1].getTime()"
        @input="handleEndChange"
      />
    </div>
  </div>
</template>

<style scoped>
.time-range-slider {
  padding: 15px 10px;
}

.date-display {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-size: 14px;
  color: #606266;
}

.slider-container {
  position: relative;
  height: 30px;
}

.slider-track {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 4px;
  background-color: #dcdfe6;
  border-radius: 2px;
  transform: translateY(-50%);
}

.slider-range {
  position: absolute;
  height: 100%;
  background-color: #409eff;
  border-radius: 2px;
}

.slider-handle {
  position: absolute;
  top: 50%;
  width: 100%;
  height: 12px;
  margin: 0;
  transform: translateY(-50%);
  background: transparent;
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
  pointer-events: none;
  z-index: 2;
}

.slider-handle::-webkit-slider-thumb {
  pointer-events: auto;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #409eff;
  cursor: pointer;
  -webkit-appearance: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.slider-handle::-moz-range-thumb {
  pointer-events: auto;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #409eff;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
</style>
