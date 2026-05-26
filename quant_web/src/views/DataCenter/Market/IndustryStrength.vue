<!-- IndustryStrength.vue - 行业强弱分析页面 - 统一样式 -->
<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  type DataTableColumns,
  NButton,
  NCard,
  NDataTable,
  NProgress,
  NSpin,
  NTag,
  NText,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";

const router = useRouter();
const message = useMessage();

interface Industry {
  code: string;
  name: string;
  change: number;
  strength: number;
  category?: string;
}

const loading = ref(false);
const error = ref<string | null>(null);
const industries = ref<Industry[]>([]);

const strongIndustriesCount = computed(() =>
  industries.value.filter((i) => i.strength > 70).length,
);
const weakIndustriesCount = computed(() =>
  industries.value.filter((i) => i.strength < 50).length,
);

const getChangeTagType = (change: number): "success" | "error" | "default" => {
  if (change > 0) return "success";
  if (change < 0) return "error";
  return "default";
};

const getProgressStatus = (strength: number): "success" | "warning" | "error" | "default" => {
  if (strength > 85) return "success";
  if (strength > 70) return "warning";
  if (strength > 50) return "default";
  return "error";
};

const getStrengthLabel = (strength: number): string => {
  if (strength > 85) return "过热";
  if (strength > 70) return "强势";
  if (strength > 50) return "正常";
  return "弱势";
};

const columns: DataTableColumns<Industry> = [
  {
    title: "行业板块", key: "name", width: 150, fixed: "left", align: "center",
    render: (row) => h("div", { class: "industry-name-cell" }, [
      h("span", { class: "industry-name" }, row.name),
      h("span", { class: "industry-code" }, row.code),
    ]),
  },
  {
    title: "涨跌幅", key: "change", width: 120, align: "center",
    render: (row) => {
      const changeText = `${row.change >= 0 ? "+" : ""}${row.change.toFixed(2)}%`;
      return h(NTag, { type: getChangeTagType(row.change), size: "small" }, {
        default: () => [
          h(SmartIcon, { name: row.change >= 0 ? "TrendingUp" : "TrendingDown", size: 14 }),
          h("span", { style: { marginLeft: "4px", fontWeight: 600 } }, changeText),
        ],
      });
    },
  },
  {
    title: "强度指数", key: "strength", width: 180, align: "center",
    render: (row) => h("div", { class: "strength-cell" }, [
      h(NProgress, { type: "line", percentage: row.strength, status: getProgressStatus(row.strength), height: 6, borderRadius: 3 }),
      h("div", { class: "strength-info" }, [
        h(NText, { depth: 1, class: "strength-value" }, { default: () => row.strength.toFixed(1) }),
        h(NText, { depth: 3, class: "strength-label" }, { default: () => getStrengthLabel(row.strength) }),
      ]),
    ]),
  },
  {
    title: "操作", key: "actions", width: 100, fixed: "right", align: "center",
    render: (row) => h(NButton, { type: "primary", size: "small", onClick: () => viewIndustryDetail(row) }, {
      default: () => [h(SmartIcon, { name: "Eye", size: 14 }), " 详情"],
    }),
  },
];

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/");
};

const loadIndustryData = async () => {
  loading.value = true;
  error.value = null;
  try {
    await new Promise((r) => setTimeout(r, 800));
    industries.value = [
      { code: "801010", name: "计算机", change: 3.2, strength: 85, category: "信息技术" },
      { code: "801020", name: "电子", change: 2.1, strength: 78, category: "信息技术" },
      { code: "801030", name: "医药生物", change: 1.8, strength: 72, category: "医疗保健" },
      { code: "801040", name: "通信", change: 1.5, strength: 68, category: "信息技术" },
      { code: "801050", name: "传媒", change: -1.2, strength: 45, category: "可选消费" },
      { code: "801060", name: "房地产", change: -2.1, strength: 35, category: "金融地产" },
      { code: "801070", name: "银行", change: 0.5, strength: 55, category: "金融地产" },
      { code: "801080", name: "证券", change: 1.2, strength: 62, category: "金融地产" },
      { code: "801090", name: "保险", change: -0.8, strength: 48, category: "金融地产" },
      { code: "801100", name: "白酒", change: 2.5, strength: 82, category: "主要消费" },
    ];
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载行业数据失败";
  } finally {
    loading.value = false;
  }
};

const refreshData = () => loadIndustryData();
const viewIndustryDetail = (industry: Industry) => message.info(`查看行业详情: ${industry.name}`);

onMounted(() => loadIndustryData());
</script>

<template>
  <div class="industry-strength-page scrollbar-hide">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">行业强弱分析</h1>
          <p class="page-description">深度分析各行业板块表现与相对强度</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 主内容 -->
    <div class="main-content">
      <n-spin :show="loading">
        <!-- Error -->
        <div v-if="error" class="error-state">
          <SmartIcon name="AlertCircle" class="error-icon" />
          <p class="error-message">{{ error }}</p>
          <n-button type="primary" @click="loadIndustryData">
            <template #icon><SmartIcon name="Refresh" /></template>
            重新加载
          </n-button>
        </div>

        <!-- Empty -->
        <div v-else-if="!loading && industries.length === 0" class="empty-state">
          <SmartIcon name="BarChart" class="empty-icon" />
          <p class="empty-message">暂无行业数据</p>
          <n-button type="primary" @click="loadIndustryData">
            <template #icon><SmartIcon name="Refresh" /></template>
            重新加载
          </n-button>
        </div>

        <!-- Data -->
        <template v-else>
          <n-card class="industry-card" title="行业强弱排名">
            <template #header-extra>
              <div class="card-stats">
                <span class="stat-item">共 <strong>{{ industries.length }}</strong> 个行业</span>
                <span class="stat-item">强势: <strong class="text-up">{{ strongIndustriesCount }}</strong></span>
                <span class="stat-item">弱势: <strong class="text-down">{{ weakIndustriesCount }}</strong></span>
              </div>
            </template>

            <n-data-table
              :columns="columns"
              :data="industries"
              :bordered="false"
              :max-height="600"
              size="small"
              striped
              flex-height
            />
          </n-card>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<style scoped lang="scss">
.industry-strength-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;

  :deep(.n-card) {
    --n-color: transparent !important;
    background: var(--color-bg-card, rgba(12, 18, 32, 0.72)) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);

    > .n-card-header,
    > .n-card__content,
    > .n-card-footer,
    > .n-card-action {
      background: transparent !important;
    }
  }
}

.card-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--n-text-color-3);

  strong {
    color: var(--n-text-color-1);
    font-weight: 600;

    &.text-up { color: var(--color-stock-up, #FF5252); }
    &.text-down { color: var(--color-stock-down, #00E676); }
  }
}

/* 表格样式 */
:deep(.industry-name-cell) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;

  .industry-name { font-weight: 600; color: var(--n-text-color-1); font-size: 14px; }
  .industry-code  { font-size: 12px; color: var(--n-text-color-3); }
}

:deep(.strength-cell) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;

  .strength-info {
    display: flex;
    gap: 8px;
    align-items: baseline;

    .strength-value { font-size: 14px; font-weight: 600; }
    .strength-label { font-size: 12px; }
  }
}

/* 状态样式 */
.error-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--n-text-color-2);
  text-align: center;
  gap: 12px;

  .error-icon, .empty-icon {
    font-size: 48px;
    opacity: 0.5;
  }
}

/* 响应式 */
@media (max-width: 768px) {
}
</style>
