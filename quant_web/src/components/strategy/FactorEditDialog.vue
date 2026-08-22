<template>
  <NModal
    v-model:show="dialogVisible"
    preset="card"
    :title="dialogTitle"
    style="width: 600px"
    @close="handleClose"
  >
    <NForm
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-placement="left"
      label-width="100px"
    >
      <NFormItem label="因子名称" path="name">
        <NInput
          v-model:value="formData.name"
          placeholder="请输入因子名称"
          maxlength="50"
          show-count
        />
      </NFormItem>

      <NFormItem label="因子代码" path="code">
        <NInput
          v-model:value="formData.code"
          placeholder="请输入因子代码"
          maxlength="20"
          show-count
        />
      </NFormItem>

      <NFormItem label="因子类别" path="category">
        <NSelect
          v-model:value="formData.category"
          :options="categoryOptions"
          placeholder="请选择因子类别"
          style="width: 100%"
        />
      </NFormItem>

      <NFormItem label="因子描述" path="description">
        <NInput
          v-model:value="formData.description"
          type="textarea"
          :rows="3"
          placeholder="请输入因子描述"
          maxlength="200"
          show-count
        />
      </NFormItem>

      <NFormItem label="数据字段" path="dataFields">
        <NSelect
          v-model:value="formData.dataFields"
          :options="dataFieldOptions"
          multiple
          placeholder="请选择所需数据字段"
          style="width: 100%"
        />
      </NFormItem>

      <NFormItem label="因子公式" path="formula">
        <NInput
          v-model:value="formData.formula"
          type="textarea"
          :rows="4"
          placeholder="请输入因子计算公式（Python语法）"
          maxlength="500"
          show-count
        />
        <div class="formula-tips">
          <Icon icon="mdi:information" />
          <span>支持Python语法，可使用选中的数据字段进行计算</span>
        </div>
      </NFormItem>

      <NFormItem label="状态" path="status">
        <NSwitch
          v-model:value="formData.status"
          :checked-value="'active'"
          :unchecked-value="'inactive'"
        />
        <span class="switch-label">{{
          formData.status === "active" ? "启用" : "停用"
        }}</span>
      </NFormItem>
    </NForm>

    <template #footer>
      <div class="dialog-footer">
        <NButton @click="handleClose">取消</NButton>
        <NButton type="primary" :loading="saving" @click="handleSave">
          <Icon icon="mdi:check" />
          保存
        </NButton>
      </div>
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
  NSelect,
  NSwitch,
  NButton,
} from "naive-ui";
import type { FormRules, FormInst } from "naive-ui";
import { Icon } from "@iconify/vue";
import { useMessage } from "naive-ui";
import dataAPI from "@/api/data";

const message = useMessage();

const props = defineProps<{
  modelValue: boolean;
  factor?: Record<string, any> | null;
  mode?: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  save: [data: any];
}>();

const formRef = ref<FormInst | null>(null);
const saving = ref(false);

const formData = reactive({
  name: "",
  code: "",
  category: "",
  description: "",
  dataFields: [] as string[],
  formula: "",
  status: "active",
});

const categoryOptions = [
  { label: "价值因子", value: "value" },
  { label: "成长因子", value: "growth" },
  { label: "质量因子", value: "quality" },
  { label: "动量因子", value: "momentum" },
  { label: "技术因子", value: "technical" },
];

const dataFieldOptions = [
  { label: "收盘价", value: "close" },
  { label: "开盘价", value: "open" },
  { label: "最高价", value: "high" },
  { label: "最低价", value: "low" },
  { label: "成交量", value: "volume" },
  { label: "市盈率", value: "pe" },
  { label: "市净率", value: "pb" },
  { label: "股息率", value: "dividend_yield" },
  { label: "ROE", value: "roe" },
  { label: "营收", value: "revenue" },
  { label: "净利润", value: "net_profit" },
];

const formRules: FormRules = {
  name: [
    { required: true, message: "请输入因子名称", trigger: "blur" },
    { min: 2, max: 50, message: "长度在 2 到 50 个字符", trigger: "blur" },
  ],
  code: [
    { required: true, message: "请输入因子代码", trigger: "blur" },
    {
      pattern: /^[A-Z0-9_]+$/,
      message: "只能包含大写字母、数字和下划线",
      trigger: "blur",
    },
  ],
  category: [{ required: true, message: "请选择因子类别", trigger: "change" }],
  description: [{ required: true, message: "请输入因子描述", trigger: "blur" }],
  dataFields: [
    {
      required: true,
      message: "请选择至少一个数据字段",
      trigger: "change",
      type: "array",
      validator: (_rule, value: string[]) => value.length > 0,
    },
  ],
  formula: [{ required: true, message: "请输入因子计算公式", trigger: "blur" }],
};

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const dialogTitle = computed(() => {
  return (props.mode || "create") === "create" ? "新建因子" : "编辑因子";
});

const handleClose = () => {
  dialogVisible.value = false;
  resetForm();
};

const resetForm = () => {
  formRef.value?.restoreValidation();
  Object.assign(formData, {
    name: "",
    code: "",
    category: "",
    description: "",
    dataFields: [],
    formula: "",
    status: "active",
  });
};

const handleSave = async () => {
  formRef.value?.validate(async (errors) => {
    if (errors) return;
    saving.value = true;
    try {
      const payload = {
        factor_code: formData.code,
        factor_name: formData.name,
        category: formData.category || undefined,
        description: formData.description || undefined,
        formula: formData.formula || undefined,
        data_requirements: formData.dataFields.length > 0 ? formData.dataFields : undefined,
        is_active: formData.status === "active",
      };
      const res = await dataAPI.createFactorDefinition(payload);
      if (res.success) {
        message.success("因子定义创建成功");
        // 提示：仅创建元数据，需后端注册计算器后才能计算/研究
        message.warning(
          "新建因子需在 quant_server/modules/data/factor_calculators.py 中用 @register_factor 注册同名计算器后，才能执行因子计算与研究",
          { duration: 8000 },
        );
        emit("save", { ...formData });
        handleClose();
      } else {
        message.error(res.message || "创建失败");
      }
    } catch (e: any) {
      message.error(e?.message || "请求失败，请检查网络");
    } finally {
      saving.value = false;
    }
  });
};

watch(
  () => props.factor,
  (newFactor) => {
    if (newFactor) {
      Object.assign(formData, {
        name: newFactor.name || "",
        code: newFactor.code || "",
        category: newFactor.category || "",
        description: newFactor.description || "",
        dataFields: newFactor.dataFields || [],
        formula: newFactor.formula || "",
        status: newFactor.status || "active",
      });
    }
  },
  { immediate: true },
);

watch(
  () => props.modelValue,
  (newVal) => {
    if (newVal && (props.mode || "create") === "create") {
      resetForm();
    }
  },
);
</script>

<style lang="scss" scoped>
.formula-tips {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 4px;
  font-size: 12px;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 6px;
}

.switch-label {
  margin-left: 8px;
  color: var(--n-text-color-3);
  font-size: 13px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>

<style>
/*
 * 因子编辑 / 因子研究弹窗：强制卡片不透明。
 * 暗色主题 CARD_BG = rgba(12,18,32,0.72) 使卡片半透明，
 * 页面 bg-gradient-mesh 背景穿透造成"玻璃态"。
 * NModal teleport body → 只能全局选择器命中。
 */
.n-modal-container .n-card,
.n-modal-container .n-modal,
.n-modal-container .n-modal-wrapper {
  background-color: rgb(12, 18, 32) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
</style>
