<script setup lang="ts">
// components/common/AppDateRangePicker.vue
// 统一日期范围选择器：内置快捷预设（今日/近7日/近30日/近90日/今年/去年）、
// 只读输入（避免手输格式错误）、统一 value-format="yyyy-MM-dd"。
// 契约（与 n-date-picker 兼容，二选一或同时绑定）：
//   v-model:value      时间戳对 [number, number] | null
//   v-model:formatted  "yyyy-MM-dd" 字符串对 [string, string] | null
import { NDatePicker } from "naive-ui";
import dayjs from "dayjs";

const props = withDefaults(
  defineProps<{
    value?: [number, number] | null;
    formatted?: [string, string] | null;
    size?: "small" | "medium" | "large";
    clearable?: boolean;
    /** 是否禁止手输，默认 true（避免格式错误） */
    inputReadonly?: boolean;
    placeholder?: string;
    style?: string | Record<string, string>;
  }>(),
  { size: "small", clearable: true, inputReadonly: true },
);

const emit = defineEmits<{
  (e: "update:value", v: [number, number] | null): void;
  (e: "update:formatted", v: [string, string] | null): void;
  (e: "update:show", v: boolean): void;
}>();

const shortcuts: Record<string, () => [number, number]> = {
  今日: () => [
    dayjs().startOf("day").valueOf(),
    dayjs().endOf("day").valueOf(),
  ],
  近7日: () => [
    dayjs().subtract(6, "day").startOf("day").valueOf(),
    dayjs().valueOf(),
  ],
  近30日: () => [
    dayjs().subtract(29, "day").startOf("day").valueOf(),
    dayjs().valueOf(),
  ],
  近90日: () => [
    dayjs().subtract(89, "day").startOf("day").valueOf(),
    dayjs().valueOf(),
  ],
  今年: () => [dayjs().startOf("year").valueOf(), dayjs().valueOf()],
  去年: () => [
    dayjs().subtract(1, "year").startOf("year").valueOf(),
    dayjs().subtract(1, "year").endOf("year").valueOf(),
  ],
};

const toFormatted = (
  v: [number, number] | null,
): [string, string] | null =>
  v
    ? [dayjs(v[0]).format("YYYY-MM-DD"), dayjs(v[1]).format("YYYY-MM-DD")]
    : null;

const toValue = (v: [string, string] | null): [number, number] | null =>
  v ? [dayjs(v[0]).valueOf(), dayjs(v[1]).valueOf()] : null;

function onUpdateValue(v: [number, number] | null) {
  emit("update:value", v);
  if (props.formatted !== undefined) emit("update:formatted", toFormatted(v));
}

function onUpdateFormatted(v: [string, string] | null) {
  emit("update:formatted", v);
  if (props.value !== undefined) emit("update:value", toValue(v));
}
</script>

<template>
  <n-date-picker
    type="daterange"
    :value="value"
    :formatted-value="formatted"
    value-format="yyyy-MM-dd"
    :size="size"
    :clearable="clearable"
    :input-readonly="inputReadonly"
    :actions="['clear', 'confirm']"
    :shortcuts="shortcuts"
    :placeholder="placeholder ?? '选择日期范围'"
    :style="style"
    @update:value="onUpdateValue"
    @update:formatted-value="onUpdateFormatted"
    @update:show="(v: boolean) => emit('update:show', v)"
  />
</template>
