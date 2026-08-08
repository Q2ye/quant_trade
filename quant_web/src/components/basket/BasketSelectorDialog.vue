<!-- BasketSelectorDialog.vue - 篮子选择弹窗 -->
<script setup lang="ts">
import { ref, watch } from "vue";
import {
  NModal,
  NCard,
  NButton,
  NInput,
  NSpin,
  NResult,
  NEmpty,
  NTag,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { getBaskets, addStockToBasket, createBasket } from "@/api/basket";
import type { Basket } from "@/types";

const props = defineProps<{
  show: boolean;
  stock: { symbol: string; name: string };
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
  added: [basketId: string];
}>();

const message = useMessage();

const loading = ref(false);
const error = ref(false);
const baskets = ref<Basket[]>([]);
const selectedId = ref<string | null>(null);
const adding = ref(false);
const newBasketName = ref("");

const fetchBaskets = async () => {
  loading.value = true;
  error.value = false;
  try {
    const result = await getBaskets();
    baskets.value = result.baskets;
    selectedId.value = null;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const handleAddToBasket = async () => {
  if (!selectedId.value) return;
  adding.value = true;
  try {
    await addStockToBasket(selectedId.value, {
      symbol: props.stock.symbol,
      weight: 0.1,
    });
    const basket = baskets.value.find((b) => b.id === selectedId.value);
    message.success(`已添加到篮子「${basket?.name ?? selectedId.value}」`);
    emit("added", selectedId.value);
    emit("update:show", false);
  } catch {
    message.error("添加失败，请重试");
  } finally {
    adding.value = false;
  }
};

const handleCreateAndAdd = async () => {
  const name = newBasketName.value.trim();
  if (!name) {
    message.warning("请输入篮子名称");
    return;
  }
  adding.value = true;
  try {
    const basket = await createBasket({
      name,
      items: [
        { symbol: props.stock.symbol, weight: 0.1, id: "", basket_id: "" },
      ],
    });
    message.success(`已创建篮子「${name}」并添加标的`);
    emit("added", basket.id);
    emit("update:show", false);
  } catch {
    message.error("创建失败，请重试");
  } finally {
    adding.value = false;
  }
};

watch(
  () => props.show,
  (val) => {
    if (val) {
      fetchBaskets();
      newBasketName.value = "";
      selectedId.value = null;
    }
  },
);
</script>

<template>
  <n-modal
    :show="show"
    :on-update:show="(v: boolean) => emit('update:show', v)"
    preset="card"
    title="加入篮子"
    style="width: 480px; max-width: 90vw"
    :bordered="false"
  >
    <n-spin :show="loading">
      <!-- Error -->
      <n-result
        v-if="error"
        status="500"
        title="加载失败"
        description="获取篮子列表失败"
      >
        <template #footer>
          <n-button type="primary" @click="fetchBaskets">重试</n-button>
        </template>
      </n-result>

      <!-- Empty -->
      <template v-else-if="!loading && baskets.length === 0">
        <n-empty description="暂无篮子" class="empty-state" />
      </template>

      <!-- Basket list -->
      <div v-else class="basket-list">
        <div
          v-for="basket in baskets"
          :key="basket.id"
          class="basket-item"
          :class="{ selected: selectedId === basket.id }"
          @click="selectedId = basket.id"
        >
          <div class="basket-info">
            <span class="basket-name">{{ basket.name }}</span>
            <n-tag size="small" :bordered="false">
              {{ basket.items?.length ?? 0 }} 只标的
            </n-tag>
          </div>
          <SmartIcon
            v-if="selectedId === basket.id"
            name="Check"
            class="check-icon"
          />
        </div>
      </div>

      <!-- Create new -->
      <div class="create-section">
        <div class="create-row">
          <n-input
            v-model:value="newBasketName"
            placeholder="输入名称快速新建篮子"
            size="small"
            :disabled="adding"
          />
          <n-button
            size="small"
            type="primary"
            :loading="adding"
            :disabled="!newBasketName.trim()"
            @click="handleCreateAndAdd"
          >
            创建并加入
          </n-button>
        </div>
      </div>
    </n-spin>

    <!-- Footer -->
    <template v-if="!loading && !error && baskets.length > 0" #footer>
      <div class="modal-footer">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button
          type="primary"
          :disabled="!selectedId"
          :loading="adding"
          @click="handleAddToBasket"
        >
          确认添加
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped lang="scss">
.basket-list {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.basket-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  border: 1px solid transparent;

  &:hover {
    background: var(--n-color-hover);
  }

  &.selected {
    background: rgba(var(--n-primary-color-rgb, 124 58 237), 0.12);
    border-color: var(--n-primary-color);
  }
}

.basket-info {
  display: flex;
  align-items: center;
  gap: 8px;

  .basket-name {
    font-weight: 500;
    color: var(--n-text-color-1);
  }
}

.check-icon {
  font-size: 20px;
  color: var(--n-primary-color);
  opacity: 0.4;

  .selected & {
    opacity: 1;
  }
}

.create-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--n-border-color);
}

.create-row {
  display: flex;
  gap: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.empty-state {
  margin: 24px 0;
}
</style>
