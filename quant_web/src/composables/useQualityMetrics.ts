import { computed, type Ref } from "vue";
import type { DataQualityResponse } from "@/api/data-sync";

/**
 * 数据质量指标统一计算 — 消除 DataSyncOverview / DataQuality 重复
 */
export function useQualityMetrics(
  qualityData: Ref<DataQualityResponse | null>,
) {
  const qualityScore = computed(() =>
    Math.round(qualityData.value?.quality_score ?? 0),
  );

  const qualityLevel = computed(() => {
    const level = qualityData.value?.quality_level || "--";
    const map: Record<string, string> = {
      excellent: "优秀",
      good: "良好",
      fair: "一般",
      poor: "较差",
    };
    return map[level] || level;
  });

  const qualityLevelClass = computed(() => {
    const score = qualityScore.value;
    if (score >= 90) return "success";
    if (score >= 70) return "warning";
    return "danger";
  });

  const qualityLevelIcon = computed(() => {
    const score = qualityScore.value;
    if (score >= 90) return "mdi:check-circle";
    if (score >= 70) return "mdi:alert-circle";
    return "mdi:close-circle";
  });

  const issuesCount = computed(() => qualityData.value?.issues?.length ?? 0);
  const metricsCount = computed(() => qualityData.value?.metrics?.length ?? 0);
  const recommendations = computed(
    () => qualityData.value?.recommendations ?? [],
  );

  const qualityCompleteness = computed(() => {
    const m = qualityData.value?.metrics?.find(
      (m) =>
        m.metric_name.includes("完整") ||
        m.metric_name.toLowerCase().includes("completeness"),
    );
    return m?.metric_value ?? 0;
  });

  const qualityTimeliness = computed(() => {
    const m = qualityData.value?.metrics?.find(
      (m) =>
        m.metric_name.includes("时效") ||
        m.metric_name.includes("及时") ||
        m.metric_name.toLowerCase().includes("timeliness"),
    );
    return m?.metric_value ?? 0;
  });

  const qualityAccuracy = computed(() => {
    const m = qualityData.value?.metrics?.find(
      (m) =>
        m.metric_name.includes("准确") ||
        m.metric_name.toLowerCase().includes("accuracy"),
    );
    return m?.metric_value ?? 0;
  });

  const qualityCheckTime = computed(() => {
    if (!qualityData.value?.generated_at) return "--";
    try {
      return new Date(qualityData.value.generated_at).toLocaleString("zh-CN");
    } catch {
      return qualityData.value.generated_at;
    }
  });

  return {
    qualityScore,
    qualityLevel,
    qualityLevelClass,
    qualityLevelIcon,
    issuesCount,
    metricsCount,
    recommendations,
    qualityCompleteness,
    qualityTimeliness,
    qualityAccuracy,
    qualityCheckTime,
  };
}
