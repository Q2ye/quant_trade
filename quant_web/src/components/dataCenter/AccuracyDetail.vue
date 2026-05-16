<template>
  <div v-if="verificationData" class="accuracy-detail">
    <div class="desc-grid">
      <div class="desc-item">
        <span class="desc-label">数据表</span
        ><span class="desc-value">{{ verificationData.tableName }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">验证类型</span>
        <span class="desc-value">
          <NTag
            :type="
              getVerificationTypeTagType(verificationData.verificationType)
            "
            size="small"
          >
            {{ getVerificationTypeText(verificationData.verificationType) }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">准确率</span>
        <span
          class="desc-value"
          :class="getRateTextClass(verificationData.accuracyRate)"
        >
          {{ verificationData.accuracyRate.toFixed(2) }}%
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">验证状态</span>
        <span class="desc-value">
          <NTag :type="getStatusTagType(verificationData.status)" size="small">
            {{ getStatusText(verificationData.status) }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">检查记录数</span
        ><span class="desc-value">{{
          formatNumber(verificationData.checkedRecords)
        }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">错误记录数</span>
        <span
          class="desc-value"
          :class="getErrorCountClass(verificationData.errorRecords)"
        >
          {{ formatNumber(verificationData.errorRecords) }}
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">最后验证时间</span
        ><span class="desc-value">{{
          verificationData.lastVerificationTime
        }}</span>
      </div>
      <div class="desc-item desc-full">
        <span class="desc-label">验证描述</span
        ><span class="desc-value">{{ verificationData.description }}</span>
      </div>
    </div>

    <div v-if="verificationData.details" class="details-section">
      <h4>验证规则详情</h4>
      <div class="desc-grid">
        <div class="desc-item desc-full">
          <span class="desc-label">规则描述</span
          ><span class="desc-value">{{
            verificationData.details.ruleDescription
          }}</span>
        </div>
        <div class="desc-item">
          <span class="desc-label">通过率</span
          ><span class="desc-value"
            >{{ verificationData.details.passRate?.toFixed(2) }}%</span
          >
        </div>
      </div>

      <div
        v-if="verificationData.details.validationRules"
        class="validation-rules"
      >
        <h5>具体验证规则</h5>
        <ul class="rules-list">
          <li
            v-for="(rule, index) in verificationData.details.validationRules"
            :key="index"
          >
            {{ rule }}
          </li>
        </ul>
      </div>

      <div v-if="verificationData.details.errorExamples" class="error-examples">
        <h5>错误示例</h5>
        <NDataTable
          :data="verificationData.details.errorExamples"
          size="small"
          :bordered="true"
          :columns="errorColumns"
        />
      </div>
    </div>

    <div class="action-section">
      <NButton type="primary" @click="handleExportReport">
        <Icon icon="mdi:file-export" class="button-icon" />导出验证报告
      </NButton>
      <NButton type="warning" @click="handleRerunVerification">
        <Icon icon="mdi:refresh" class="button-icon" />重新验证
      </NButton>
      <NButton @click="handleViewRules">
        <Icon icon="mdi:eye" class="button-icon" />查看验证规则
      </NButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NTag, NButton, NDataTable } from "naive-ui";
import { useMessage } from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";

const message = useMessage();

defineProps<{ verificationData: any }>();

const errorColumns = computed<DataTableColumn<any>[]>(() => {
  // Will be populated dynamically when errorExamples exist
  return [];
});

const getVerificationTypeTagType = (type: string) => {
  const typeMap: Record<string, "info" | "success" | "warning" | "error"> = {
    consistency: "info",
    business_logic: "success",
    data_range: "warning",
    data_relation: "info",
  };
  return typeMap[type] || "default";
};

const getVerificationTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    consistency: "数据一致性",
    business_logic: "业务逻辑",
    data_range: "数据范围",
    data_relation: "数据关联",
  };
  return textMap[type] || type;
};

const getStatusTagType = (status: string) => {
  const statusMap: Record<string, "success" | "warning" | "error"> = {
    accurate: "success",
    warning: "warning",
    error: "error",
  };
  return statusMap[status] || "default";
};

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    accurate: "准确",
    warning: "警告",
    error: "错误",
  };
  return textMap[status] || status;
};

const getRateTextClass = (rate: number) => {
  if (rate >= 99) return "rate-high";
  if (rate >= 95) return "rate-medium";
  return "rate-low";
};

const getErrorCountClass = (count: number) => {
  if (count === 0) return "error-zero";
  if (count < 1000) return "error-low";
  return "error-high";
};

const formatNumber = (num: number) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
};

const handleExportReport = () => message.success("导出验证报告功能开发中");
const handleRerunVerification = () => message.success("重新验证功能开发中");
const handleViewRules = () => message.success("查看验证规则功能开发中");
</script>

<style scoped>
.accuracy-detail {
  padding: 0;
}

.desc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--n-border-color);
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
}

.desc-item {
  display: flex;
  background: var(--n-body-color);
  padding: 8px 12px;
}

.desc-label {
  color: var(--n-text-color-3);
  min-width: 90px;
  font-size: 13px;
}

.desc-value {
  color: var(--n-text-color-1);
  font-size: 13px;
}

.desc-full {
  grid-column: 1 / -1;
}

.details-section {
  margin-top: 20px;
}
.details-section h4 {
  margin: 0 0 12px 0;
  color: var(--n-text-color-2);
}
.validation-rules {
  margin-top: 16px;
}
.validation-rules h5 {
  margin: 16px 0 8px 0;
  color: var(--n-text-color-2);
}
.rules-list {
  padding-left: 20px;
  color: var(--n-text-color-2);
}
.rules-list li {
  margin-bottom: 4px;
  line-height: 1.4;
}
.error-examples {
  margin-top: 16px;
}
.error-examples h5 {
  margin: 16px 0 8px 0;
  color: var(--n-text-color-2);
}
.action-section {
  margin-top: 20px;
  text-align: center;
  display: flex;
  gap: 8px;
  justify-content: center;
}
.button-icon {
  margin-right: 4px;
}
.rate-high {
  color: #67c23a;
  font-weight: 500;
}
.rate-medium {
  color: #e6a23c;
  font-weight: 500;
}
.rate-low {
  color: #f56c6c;
  font-weight: 500;
}
.error-zero {
  color: #67c23a;
}
.error-low {
  color: #e6a23c;
}
.error-high {
  color: #f56c6c;
  font-weight: 500;
}
</style>
