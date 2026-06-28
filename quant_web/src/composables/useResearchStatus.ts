import type { ResearchStatus } from "@/types/api-research";

export function useResearchStatus() {
  const statusTagType = (
    status: ResearchStatus | string,
  ): "info" | "success" | "error" | "default" | "warning" => {
    const map: Record<string, "info" | "success" | "error" | "default" | "warning"> = {
      running: "info",
      completed: "success",
      failed: "error",
      cancelled: "default",
      pending: "warning",
    };
    return map[status] || "default";
  };

  const statusLabel = (status: ResearchStatus | string): string => {
    const map: Record<string, string> = {
      running: "运行中",
      completed: "已完成",
      failed: "失败",
      cancelled: "已取消",
      pending: "等待中",
    };
    return map[status] || status;
  };

  return { statusTagType, statusLabel };
}
