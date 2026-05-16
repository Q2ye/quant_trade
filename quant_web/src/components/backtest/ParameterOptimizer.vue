<template>
  <div class="parameter-optimizer">
    <NForm label-placement="left" label-width="120px">
      <NFormItem label="优化参数">
        <div
          v-for="(param, index) in optimizationParams.parameters"
          :key="index"
          class="param-item"
        >
          <NInput
            v-model:value="param.name"
            placeholder="参数名"
            style="width: 120px"
          />
          <NInputNumber
            v-model:value="param.min"
            :min="0"
            :step="1"
            placeholder="最小值"
          />
          <NInputNumber
            v-model:value="param.max"
            :min="param.min + 1"
            :step="1"
            placeholder="最大值"
          />
          <NInputNumber
            v-model:value="param.step"
            :min="1"
            :step="1"
            placeholder="步长"
          />
          <NButton type="error" @click="removeParameter(index)">删除</NButton>
        </div>
        <NButton type="primary" @click="addParameter">添加参数</NButton>
      </NFormItem>

      <NFormItem label="优化目标">
        <NSelect
          v-model:value="optimizationParams.objective"
          :options="objectiveOptions"
        />
      </NFormItem>

      <NFormItem label="最大迭代次数">
        <NInputNumber
          v-model:value="optimizationParams.maxIterations"
          :min="10"
          :max="1000"
        />
      </NFormItem>

      <NFormItem>
        <NButton type="primary" :loading="optimizing" @click="runOptimization">
          开始优化
        </NButton>
      </NFormItem>
    </NForm>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from "vue";
import {
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NButton,
  useMessage,
} from "naive-ui";

defineProps<{
  strategy?: Record<string, any> | null;
}>();

const emit = defineEmits<{
  optimize: [params: any];
}>();

const message = useMessage();

const optimizationParams = reactive({
  parameters: [] as Array<{
    name: string;
    min: number;
    max: number;
    step: number;
  }>,
  objective: "sharpe",
  maxIterations: 100,
});

const optimizing = ref(false);

const objectiveOptions = [
  { label: "夏普比率", value: "sharpe" },
  { label: "年化收益率", value: "annualReturn" },
  { label: "卡玛比率", value: "calmar" },
  { label: "最大回撤", value: "maxDrawdown" },
];

const addParameter = () => {
  optimizationParams.parameters.push({ name: "", min: 0, max: 100, step: 1 });
};

const removeParameter = (index: number) => {
  optimizationParams.parameters.splice(index, 1);
};

const runOptimization = async () => {
  if (optimizationParams.parameters.length === 0) {
    message.warning("请至少添加一个优化参数");
    return;
  }
  optimizing.value = true;
  try {
    emit("optimize", { ...optimizationParams });
  } catch (error: any) {
    message.error("优化失败: " + error.message);
  } finally {
    optimizing.value = false;
  }
};

onMounted(() => {
  addParameter();
});
</script>

<style scoped>
.parameter-optimizer {
  padding: 20px;
  background: var(--n-color-embedded);
  border-radius: 4px;
}

.param-item {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}
</style>
