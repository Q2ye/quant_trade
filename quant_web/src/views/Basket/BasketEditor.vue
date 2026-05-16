<template>
  <div class="basket-editor bg-gradient-mesh bg-noise">
    <div class="back-header">
      <n-button text @click="$router.go(-1)">
        <Icon icon="ant-design:arrow-left-outlined" /> 返回
      </n-button>
      <span class="back-title">{{ isEditMode ? "编辑篮子" : "新建篮子" }}</span>
    </div>

    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取篮子信息失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="getBasketDetail(route.params.id as string)"
          >重试</n-button
        ></template
      >
    </n-result>

    <n-spin v-else :show="loading">
      <n-form
        :model="basket"
        :rules="rules"
        label-placement="top"
        class="basket-form"
      >
        <n-form-item label="篮子名称" path="name">
          <n-input
            v-model:value="basket.name"
            placeholder="请输入篮子名称"
            maxlength="50"
            show-count
          />
        </n-form-item>

        <n-form-item label="描述">
          <n-input
            v-model:value="basket.description"
            type="textarea"
            :rows="3"
            placeholder="请输入篮子描述"
            maxlength="200"
            show-count
          />
        </n-form-item>

        <n-form-item label="添加成分股">
          <div class="stock-search">
            <n-space :size="8">
              <n-input
                v-model:value="searchCode"
                placeholder="输入股票代码"
                size="small"
                style="width: 160px"
              />
              <n-button size="small" type="primary" @click="quickAddStock"
                >添加</n-button
              >
            </n-space>
          </div>
        </n-form-item>

        <n-divider>成分股权重设置</n-divider>

        <div class="stocks-list">
          <div v-if="basket.items.length === 0" class="empty-tip">
            请添加成分股
          </div>
          <div
            v-for="(item, index) in basket.items"
            :key="index"
            class="stock-item"
          >
            <div class="stock-info">
              <span class="code">{{ item.ts_code }}</span>
              <span class="name">{{ item.name }}</span>
            </div>
            <div class="weight-control">
              <n-input-number
                v-model:value="item.weight"
                :min="0"
                :max="1"
                :step="0.01"
                size="small"
                style="width: 120px"
              />
              <span class="percent">%</span>
            </div>
            <n-button
              type="error"
              circle
              size="tiny"
              @click="handleRemoveStock(Number(index))"
              >✕</n-button
            >
          </div>
        </div>

        <div class="form-actions">
          <n-space justify="center" :size="12">
            <n-button type="primary" @click="saveBasket">保存</n-button>
            <n-button @click="$router.go(-1)">取消</n-button>
          </n-space>
        </div>
      </n-form>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMessage, NResult } from "naive-ui";
import { Icon } from "@iconify/vue";
import { getBasket, createBasket, updateBasket } from "@/api/basket";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const basket = ref<any>({ id: null, name: "", description: "", items: [] });
const isEditMode = ref(false);
const loading = ref(false);
const error = ref(false);
const searchCode = ref("");

const rules = {
  name: [{ required: true, message: "请输入篮子名称", trigger: "blur" }],
};

const getBasketDetail = async (basketId: string) => {
  loading.value = true;
  try {
    basket.value = await getBasket(basketId);
    error.value = false;
  } catch (err) {
    console.error("获取篮子详情失败:", err);
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const quickAddStock = () => {
  const code = searchCode.value.trim();
  if (!code) {
    message.warning("请输入股票代码");
    return;
  }
  if (basket.value.items.some((item: any) => item.ts_code === code)) {
    message.warning("该股票已在篮子中");
    return;
  }
  basket.value.items.push({ ts_code: code, name: code, weight: 0 });
  searchCode.value = "";
};

const handleRemoveStock = (index: number) =>
  basket.value.items.splice(index, 1);

const saveBasket = async () => {
  if (!basket.value.name) {
    message.warning("请输入篮子名称");
    return;
  }
  const totalWeight = basket.value.items.reduce(
    (sum: number, item: any) => sum + (item.weight || 0),
    0,
  );
  if (basket.value.items.length > 0 && Math.abs(totalWeight - 1) > 0.01) {
    message.error("成分股权重总和必须为100%");
    return;
  }
  loading.value = true;
  try {
    if (isEditMode.value) {
      await updateBasket(basket.value.id, basket.value);
      message.success("篮子更新成功");
    } else {
      await createBasket(basket.value);
      message.success("篮子创建成功");
    }
    router.push({ name: "BasketList" });
  } catch (error) {
    console.error("保存失败:", error);
    message.error("保存失败");
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  const basketId = route.params.id as string;
  if (basketId) {
    isEditMode.value = true;
    getBasketDetail(basketId);
  }
});
</script>

<style scoped>
.basket-editor {
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.back-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--n-border-color);
}
.back-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.basket-form {
  margin-top: 20px;
  max-width: 800px;
}
.stocks-list {
  margin-top: 20px;
}
.stock-item {
  display: flex;
  align-items: center;
  padding: 12px 15px;
  margin-bottom: 10px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  background: var(--n-color-embedded);
}
.stock-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.stock-info .code {
  font-weight: bold;
  margin-bottom: 4px;
}
.stock-info .name {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.weight-control {
  display: flex;
  align-items: center;
  margin: 0 20px;
}
.weight-control .percent {
  margin-left: 8px;
  width: 30px;
}
.empty-tip {
  text-align: center;
  padding: 20px;
  color: var(--n-text-color-3);
  border: 1px dashed var(--n-border-color);
  border-radius: 4px;
  background: var(--n-color-embedded);
}
.form-actions {
  margin-top: 30px;
}
.stock-search {
  padding: 8px 0;
}
</style>
