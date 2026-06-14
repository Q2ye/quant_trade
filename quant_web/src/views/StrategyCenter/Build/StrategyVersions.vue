<!--
  StrategyVersions.vue — 策略版本管理页
  路由: /strategies/versions/:id
  数据源: GET /quantTrade/strategy/{id}/versions
-->
<template>
  <div class="versions-page scrollbar-hide">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <n-button quaternary @click="goBack" class="back-btn">
            <template #icon><Icon icon="mdi:arrow-left" /></template>
          </n-button>
          <div>
            <h1 class="page-title">{{ strategyName }} · 版本历史</h1>
            <p class="page-description">
              查看历史版本、对比代码变更、回测指定版本
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 主体 -->
    <div class="main-content">
      <n-space vertical :size="16">
        <!-- Loading -->
        <template v-if="loading">
          <n-card :class="tokens.surface.card">
            <n-skeleton text :repeat="6" />
          </n-card>
        </template>

        <!-- Error -->
        <n-result
          v-else-if="error"
          status="500"
          title="加载失败"
          description="无法获取策略版本数据"
        >
          <template #footer>
            <n-button type="primary" @click="loadVersions">重试</n-button>
          </template>
        </n-result>

        <!-- Empty -->
        <n-empty v-else-if="versions.length === 0" description="暂无版本记录" />

        <!-- 版本列表 -->
        <template v-else>
          <n-card :class="tokens.surface.card">
            <n-data-table
              :columns="columns"
              :data="versions"
              :row-key="(row: any) => row.version"
              :checked-row-keys="selectedKeys"
              :row-props="(row: any) => ({
                style: 'cursor: pointer',
                onClick: () => toggleSelection(row),
              })"
              :bordered="false"
              size="small"
              max-height="400"
            />
          </n-card>

          <!-- 版本对比 -->
          <n-card
            v-if="selectedKeys.length === 2"
            :class="tokens.surface.card"
            title="版本对比"
          >
            <template #header-extra>
              <n-tag type="info">{{ compareOld?.version }}</n-tag>
              <span style="margin: 0 8px; color: var(--color-text-tertiary)">→</span>
              <n-tag type="success">{{ compareNew?.version }}</n-tag>
            </template>
            <CodeDiff
              :old-code="compareOld?.code || ''"
              :new-code="compareNew?.code || ''"
              language="python"
              style="max-height: 500px"
            />
          </n-card>
        </template>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { tokens } from "@/styles/design-tokens";
import { Icon } from "@iconify/vue";
import CodeDiff from "@/components/common/CodeDiff.vue";
import strategyAPI from "@/api/strategy";

const route = useRoute();
const router = useRouter();

const strategyId = computed(() => route.params.id as string);
const strategyName = ref("策略");

const loading = ref(true);
const error = ref(false);
const versions = ref<any[]>([]);
const selectedKeys = ref<string[]>([]);

const columns = [
  {
    title: "版本",
    key: "version",
    width: 120,
    render: (row: any) =>
      row.is_current
        ? h("span", [h("strong", row.version), h("span", { style: { marginLeft: "8px" } }, "✅ 当前")])
        : row.version,
  },
  { title: "更新时间", key: "created_at", width: 180,
    render: (row: any) => row.created_at ? new Date(row.created_at).toLocaleString("zh-CN") : "--" },
  { title: "说明", key: "description", ellipsis: { tooltip: true } },
  {
    title: "操作",
    key: "actions",
    width: 180,
    render: (row: any) =>
      h("span", { style: { display: "flex", gap: "8px" } }, [
        h(
          "button",
          { class: "n-button n-button--default-type n-button--tiny-type", onClick: () => router.push(`/backtest/config?strategy=${strategyId.value}&version=${row.version}`) },
          "回测"
        ),
        h(
          "button",
          { class: "n-button n-button--default-type n-button--tiny-type", onClick: () => toggleSelection(row) },
          selectedKeys.value.includes(row.version) ? "已选" : "对比"
        ),
      ]),
  },
];

const compareOld = computed(() => versions.value.find((v) => v.version === selectedKeys.value[0]));
const compareNew = computed(() => versions.value.find((v) => v.version === selectedKeys.value[1]));

const toggleSelection = (row: any) => {
  const key = row.version;
  if (selectedKeys.value.includes(key)) {
    selectedKeys.value = selectedKeys.value.filter((k) => k !== key);
  } else if (selectedKeys.value.length < 2) {
    selectedKeys.value = [...selectedKeys.value, key];
  } else {
    selectedKeys.value = [selectedKeys.value[1], key];
  }
};

const goBack = () => router.push("/strategies");

const loadVersions = async () => {
  if (!strategyId.value) return;
  loading.value = true;
  error.value = false;
  try {
    const data = await strategyAPI.getStrategy(strategyId.value).catch(() => null);
    if (data) {
      strategyName.value = (data as any).name || strategyId.value;
    }
    const vers = await strategyAPI.getStrategyVersions?.(strategyId.value).catch(() => []) ?? [];
    versions.value = Array.isArray(vers) ? vers : [];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadVersions();
});
</script>

<style lang="scss" scoped>
.versions-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
  animation: fadeIn 0.3s ease-out;
}

.page-header {
  padding: 24px 32px 0;
  .header-content {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }
  .title-section {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    .back-btn { margin-top: -4px; flex-shrink: 0; }
  }
  .page-title { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: var(--color-text-primary); }
  .page-description { font-size: 13px; color: var(--color-text-tertiary); margin: 0; }
}

.main-content {
  padding: 20px 32px 32px;
}
</style>
