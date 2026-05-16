<template>
  <div class="basket-list bg-gradient-mesh bg-noise">
    <div class="header">
      <h2>股票篮子管理</h2>
      <n-button type="primary" @click="handleCreate">新建篮子</n-button>
    </div>

    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取篮子列表失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="getBasketList">重试</n-button></template
      >
    </n-result>

    <template v-else>
      <n-data-table
        :loading="loading"
        :data="baskets"
        :columns="columns"
        :bordered="false"
        striped
        :row-key="(row: any) => row.id"
      />

      <div class="pagination">
        <n-pagination
          v-model:page="pagination.page"
          :page-size="pagination.pageSize"
          :item-count="pagination.total"
          :page-sizes="[10, 20, 50]"
          show-size-picker
          @update:page="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, h } from "vue";
import { useRouter } from "vue-router";
import { useMessage, useDialog, NButton, NResult } from "naive-ui";
import { getBaskets, deleteBasket } from "@/api/basket";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const loading = ref(false);
const error = ref(false);
const baskets = ref<any[]>([]);
const pagination = ref({ page: 1, pageSize: 10, total: 0 });

const columns = [
  { title: "篮子名称", key: "name", minWidth: 150 },
  {
    title: "创建时间",
    key: "created_at",
    minWidth: 150,
    render(row: any) {
      return formatDate(row.created_at);
    },
  },
  {
    title: "成分股数量",
    key: "items_count",
    minWidth: 120,
    render(row: any) {
      return `${row.items_count || 0} 只`;
    },
  },
  {
    title: "操作",
    key: "actions",
    minWidth: 200,
    render(row: any) {
      return h("div", { style: { display: "flex", gap: "8px" } }, [
        h(
          NButton,
          {
            size: "tiny",
            type: "primary",
            onClick: () => handleViewDetail(row.id),
          },
          { default: () => "详情" },
        ),
        h(
          NButton,
          { size: "tiny", onClick: () => handleEdit(row.id) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { size: "tiny", type: "error", onClick: () => handleDelete(row.id) },
          { default: () => "删除" },
        ),
      ]);
    },
  },
];

const getBasketList = async () => {
  loading.value = true;
  try {
    const params: any = {
      page: Number(pagination.value.page) || 1,
      pageSize: Number(pagination.value.pageSize) || 10,
    };
    const res: any = await getBaskets(params);
    baskets.value = res.baskets;
    pagination.value.total = res.total;
    error.value = false;
  } catch (err) {
    console.error("获取篮子列表失败:", err);
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleCreate = () => router.push({ name: "BasketEditor" });
const handleEdit = (id: string) =>
  router.push({ name: "BasketEditor", params: { id } });
const handleViewDetail = (id: string) =>
  router.push({ name: "BasketDetail", params: { id } });

const handleDelete = (id: string) => {
  dialog.warning({
    title: "提示",
    content: "确定删除该篮子吗？",
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await deleteBasket(id);
        message.success("删除成功");
        getBasketList();
      } catch (error) {
        console.error("删除失败:", error);
        message.error("删除失败");
      }
    },
  });
};

const handlePageChange = (page: number) => {
  pagination.value.page = Number(page) || 1;
  getBasketList();
};
const handlePageSizeChange = (size: number) => {
  pagination.value.pageSize = size;
  pagination.value.page = 1;
  getBasketList();
};

const formatDate = (dateString: string) => {
  if (!dateString) return "";
  try {
    return new Date(dateString).toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return dateString;
  }
};

getBasketList();
</script>

<style scoped>
.basket-list {
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
