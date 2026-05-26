<template>
  <div v-if="anomalyData" class="anomaly-detail">
    <div class="desc-grid">
      <div class="desc-item">
        <span class="desc-label">数据表</span
        ><span class="desc-value">{{ anomalyData.tableName }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">异常类型</span>
        <span class="desc-value">
          <NTag
            :type="getAnomalyTypeTagType(anomalyData.anomalyType)"
            size="small"
          >
            {{ getAnomalyTypeText(anomalyData.anomalyType) }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">严重程度</span>
        <span class="desc-value">
          <NTag :type="getSeverityTagType(anomalyData.severity)" size="small">
            {{ getSeverityText(anomalyData.severity) }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">处理状态</span>
        <span class="desc-value">
          <NTag :type="getStatusTagType(anomalyData.status)" size="small">
            {{ getStatusText(anomalyData.status) }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">检测时间</span
        ><span class="desc-value">{{ anomalyData.detectedTime }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">影响记录数</span
        ><span class="desc-value"
          >{{ anomalyData.affectedRecords || 0 }} 条</span
        >
      </div>
      <div class="desc-item desc-full">
        <span class="desc-label">异常描述</span
        ><span class="desc-value">{{ anomalyData.description }}</span>
      </div>
      <div class="desc-item desc-full">
        <span class="desc-label">建议操作</span
        ><span class="desc-value">{{ anomalyData.suggestedAction }}</span>
      </div>
    </div>

    <div v-if="anomalyData.details" class="details-section">
      <h4>异常详情</h4>
      <div class="desc-grid">
        <div v-if="anomalyData.details.fieldName" class="desc-item desc-full">
          <span class="desc-label">字段名称</span
          ><span class="desc-value">{{ anomalyData.details.fieldName }}</span>
        </div>
        <div
          v-if="anomalyData.details.expectedValue"
          class="desc-item desc-full"
        >
          <span class="desc-label">预期值</span
          ><span class="desc-value">{{
            anomalyData.details.expectedValue
          }}</span>
        </div>
        <div v-if="anomalyData.details.actualValue" class="desc-item desc-full">
          <span class="desc-label">实际值</span
          ><span class="desc-value">{{ anomalyData.details.actualValue }}</span>
        </div>
        <div v-if="anomalyData.details.errorCount" class="desc-item">
          <span class="desc-label">错误数量</span
          ><span class="desc-value"
            >{{ anomalyData.details.errorCount }} 条</span
          >
        </div>
      </div>

      <div v-if="anomalyData.details.sampleRecords" class="sample-records">
        <h5>异常记录示例</h5>
        <NDataTable
          :data="anomalyData.details.sampleRecords"
          size="small"
          :bordered="true"
          :columns="sampleColumns"
        />
      </div>
    </div>

    <div class="action-section">
      <NButton type="primary" @click="handleExportAnomaly">
        <Icon icon="mdi:file-export" class="button-icon" />导出异常详情
      </NButton>
      <NButton
        v-if="anomalyData.status === 'pending'"
        type="success"
        @click="handleMarkResolved"
      >
        <Icon icon="mdi:check-circle" class="button-icon" />标记为已解决
      </NButton>
      <NButton
        v-if="anomalyData.status === 'pending'"
        type="warning"
        @click="handleIgnore"
      >
        <Icon icon="mdi:eye-off" class="button-icon" />忽略此异常
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
defineProps<{ anomalyData: any }>();

const sampleColumns = computed<DataTableColumn<any>[]>(() => []);

const getAnomalyTypeTagType = (type: string) => {
  const typeMap: Record<string, "warning" | "error" | "info"> = {
    missing: "warning",
    outlier: "error",
    format: "info",
    logic: "error",
    duplicate: "warning",
  };
  return typeMap[type] || "default";
};

const getAnomalyTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    missing: "数据缺失",
    outlier: "数据异常",
    format: "格式错误",
    logic: "逻辑错误",
    duplicate: "重复数据",
  };
  return textMap[type] || type;
};

const getSeverityTagType = (severity: string) => {
  const severityMap: Record<string, "info" | "warning" | "error"> = {
    low: "info",
    medium: "warning",
    high: "error",
    critical: "error",
  };
  return severityMap[severity] || "default";
};

const getSeverityText = (severity: string) => {
  const textMap: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };
  return textMap[severity] || severity;
};

const getStatusTagType = (status: string) => {
  const statusMap: Record<string, "warning" | "success" | "info"> = {
    pending: "warning",
    resolved: "success",
    ignored: "info",
  };
  return statusMap[status] || "default";
};

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: "待处理",
    resolved: "已解决",
    ignored: "已忽略",
  };
  return textMap[status] || status;
};

const handleExportAnomaly = () => message.success("导出异常详情功能开发中");
const handleMarkResolved = () => message.success("标记解决功能开发中");
const handleIgnore = () => message.success("忽略异常功能开发中");
</script>

<style scoped>
.anomaly-detail {
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
  min-width: 80px;
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
.sample-records {
  margin-top: 16px;
}
.sample-records h5 {
  margin: 16px 0 8px 0;
  color: var(--n-text-color-2);
}
.action-section {
  margin-top: 20px;
  display: flex;
  gap: 8px;
  justify-content: center;
}
.button-icon {
  margin-right: 4px;
}
</style>
