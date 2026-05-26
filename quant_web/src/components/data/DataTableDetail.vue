<template>
  <div v-if="tableData" class="data-table-detail">
    <div class="desc-grid">
      <div class="desc-item">
        <span class="desc-label">表名</span
        ><span class="desc-value">{{ tableData.tableName }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">描述</span
        ><span class="desc-value">{{ tableData.tableDescription }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">数据类型</span>
        <span class="desc-value">
          <NTag :type="getDataTypeTagType(tableData.dataType)" size="small">
            {{ getDataTypeText(tableData.dataType) }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">是否核心表</span>
        <span class="desc-value">
          <NTag
            :type="tableData.isCoreTable ? 'success' : 'default'"
            size="small"
          >
            <Icon icon="mdi:star" class="tag-icon" />
            {{ tableData.isCoreTable ? "是" : "否" }}
          </NTag>
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">总记录数</span
        ><span class="desc-value">{{
          formatNumber(tableData.totalRecords)
        }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">预期记录数</span
        ><span class="desc-value">{{
          formatNumber(tableData.expectedRecords)
        }}</span>
      </div>
      <div class="desc-item">
        <span class="desc-label">完整率</span>
        <span
          class="desc-value"
          :class="getRateTextClass(tableData.completenessRate)"
        >
          {{ tableData.completenessRate.toFixed(2) }}%
        </span>
      </div>
      <div class="desc-item">
        <span class="desc-label">缺失记录数</span>
        <span class="desc-value">{{
          formatNumber(tableData.expectedRecords - tableData.totalRecords)
        }}</span>
      </div>
      <div class="desc-item desc-full">
        <span class="desc-label">最后更新时间</span>
        <span class="desc-value"
          ><Icon icon="mdi:clock-outline" class="desc-icon" />{{
            tableData.lastUpdateTime
          }}</span
        >
      </div>
      <div class="desc-item desc-full">
        <span class="desc-label">数据新鲜度</span>
        <span class="desc-value">
          <NTag
            :type="getFreshnessTagType(tableData.dataFreshness)"
            size="small"
          >
            <Icon icon="mdi:update" class="tag-icon" />{{
              getFreshnessText(tableData.dataFreshness)
            }}
          </NTag>
        </span>
      </div>
    </div>

    <div
      v-if="tableData.missingPeriods && tableData.missingPeriods.length > 0"
      class="missing-section"
    >
      <h4><Icon icon="mdi:alert-circle" class="section-icon" />缺失时段详情</h4>
      <div class="timeline">
        <div
          v-for="(period, index) in tableData.missingPeriods"
          :key="index"
          class="timeline-item"
        >
          <div class="timeline-dot warning"></div>
          <div class="timeline-content">
            <div class="timeline-time">{{ period }}</div>
            <span
              ><Icon
                icon="mdi:calendar-remove"
                class="timeline-icon"
              />数据缺失</span
            >
          </div>
        </div>
      </div>
    </div>

    <div class="action-section">
      <NButton type="primary" @click="handleExportReport">
        <Icon icon="mdi:file-export" class="button-icon" />导出报告
      </NButton>
      <NButton type="warning" @click="handleSyncNow">
        <Icon icon="mdi:sync" class="button-icon" />立即同步
      </NButton>
      <NButton @click="handleViewSchema">
        <Icon icon="mdi:table-eye" class="button-icon" />查看表结构
      </NButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NTag, NButton } from "naive-ui";
import { useMessage } from "naive-ui";
import { Icon } from "@iconify/vue";

const message = useMessage();
defineProps<{ tableData: any }>();

const getDataTypeTagType = (type: string) => {
  const typeMap: Record<string, "info" | "success" | "warning"> = {
    market: "info",
    financial: "success",
    basic: "info",
    etf: "warning",
  };
  return typeMap[type] || "default";
};

const getDataTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    market: "行情数据",
    financial: "财务数据",
    basic: "基础信息",
    etf: "ETF数据",
  };
  return textMap[type] || type;
};

const getRateTextClass = (rate: number) => {
  if (rate >= 98) return "rate-high";
  if (rate >= 95) return "rate-medium";
  return "rate-low";
};

const getFreshnessTagType = (freshness: string) => {
  const freshnessMap: Record<string, "success" | "warning" | "error"> = {
    fresh: "success",
    stale: "warning",
    outdated: "error",
  };
  return freshnessMap[freshness] || "default";
};

const getFreshnessText = (freshness: string) => {
  const textMap: Record<string, string> = {
    fresh: "最新",
    stale: "较旧",
    outdated: "过时",
  };
  return textMap[freshness] || freshness;
};

const formatNumber = (num: number) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
};

const handleExportReport = () => message.success("导出报告功能开发中");
const handleSyncNow = () => message.success("开始同步数据...");
const handleViewSchema = () => message.success("查看表结构功能开发中");
</script>

<style scoped>
.data-table-detail {
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
  min-width: 85px;
  font-size: 13px;
}

.desc-value {
  color: var(--n-text-color-1);
  font-size: 13px;
}

.desc-full {
  grid-column: 1 / -1;
}

.missing-section {
  margin-top: 20px;
  padding: 16px;
  background-color: var(--n-color-embedded);
  border-radius: 4px;
}

.missing-section h4 {
  margin: 0 0 12px 0;
  color: var(--n-text-color-2);
  display: flex;
  align-items: center;
}
.section-icon {
  margin-right: 8px;
}

.timeline {
  position: relative;
  padding-left: 24px;
}

.timeline::before {
  content: "";
  position: absolute;
  left: 8px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: var(--n-border-color);
}

.timeline-item {
  position: relative;
  padding-bottom: 12px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: -16px;
  top: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--n-body-color);
  z-index: 1;
}

.timeline-dot.warning {
  background: #e6a23c;
}

.timeline-time {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 2px;
}

.timeline-icon {
  margin-right: 4px;
}
.desc-icon {
  margin-right: 4px;
}
.tag-icon {
  margin-right: 2px;
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
</style>
