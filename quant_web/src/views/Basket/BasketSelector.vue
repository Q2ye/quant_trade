<template>
  <div class="basket-selector">
    <div class="selector-header">
      <el-select
          v-model="selectedBasket"
          placeholder="选择股票篮子"
          @change="handleBasketChange"
          size="small"
          style="width: 300px;"
      >
        <el-option
            v-for="basket in baskets"
            :key="basket.id"
            :label="basket.name"
            :value="basket.id"
        >
          <span style="float: left">{{ basket.name }}</span>
          <span style="float: right; color: #8492a6; font-size: 13px">
            {{ basket.count }} 只股票
          </span>
        </el-option>
      </el-select>

      <el-button
          type="primary"
          icon="el-icon-plus"
          size="small"
          style="margin-left: 10px;"
          @click="createNewBasket"
      >
        新建篮子
      </el-button>
    </div>

    <div class="basket-content" v-if="currentBasket">
      <div class="basket-info">
        <h3>{{ currentBasket.name }}</h3>
        <p class="description">{{ currentBasket.description || '暂无描述' }}</p>
        <p class="stats">
          创建于: {{ currentBasket.createdAt }} |
          股票数: {{ currentBasket.stocks.length }} |
          最后更新: {{ currentBasket.updatedAt }}
        </p>
      </div>

      <div class="basket-stocks">
        <el-table
            :data="currentBasket.stocks"
            height="300"
            stripe
            highlight-current-row
            @row-click="handleStockClick"
        >
          <el-table-column prop="symbol" label="代码" width="80"></el-table-column>
          <el-table-column prop="name" label="名称" width="120"></el-table-column>
          <el-table-column label="权重" width="100">
            <template #default="{ row }">
              <el-input-number
                  v-model="row.weight"
                  :min="0"
                  :max="100"
                  :precision="1"
                  :step="1"
                  size="small"
                  controls-position="right"
                  @change="updateWeight(row)"
              ></el-input-number>
              <span>%</span>
            </template>
          </el-table-column>
          <el-table-column label="当前价" width="100">
            <template #default="{ row }">
              {{ row.lastPrice ? row.lastPrice.toFixed(2) : '--' }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100">
            <template #default="{ row }">
              <span :class="row.change >= 0 ? 'up' : 'down'">
                {{ row.change >= 0 ? '+' : '' }}{{ row.change ? row.change.toFixed(2) : '0.00' }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button
                  type="danger"
                  icon="el-icon-delete"
                  circle
                  size="small"
                  @click.stop="removeStock(row)"
              ></el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="basket-actions">
        <el-button
            type="primary"
            icon="el-icon-shopping-cart-2"
            @click="applyToTrade"
            :disabled="!currentBasket.stocks.length"
        >
          应用至交易
        </el-button>
        <el-button
            icon="el-icon-download"
            @click="exportBasket"
        >
          导出篮子
        </el-button>
        <el-button
            type="danger"
            icon="el-icon-delete"
            style="float: right;"
            @click="deleteBasket"
        >
          删除篮子
        </el-button>
      </div>
    </div>

    <div class="empty-basket" v-else>
      <el-empty description="请选择或创建股票篮子"></el-empty>
    </div>
  </div>
</template>

<script>
import {ref} from 'vue';

export default {
  name: "BasketSelector",
  setup(_, {emit}) { // 删除未使用的props参数
    const baskets = ref([
      {
        id: '1',
        name: '核心资产组合',
        description: '长期持有的核心资产',
        count: 5,
        createdAt: '2023-07-15',
        updatedAt: '2023-08-10',
        stocks: [
          {symbol: '600519.SH', name: '贵州茅台', weight: 25, lastPrice: 1850.50, change: 1.25},
          {symbol: '600036.SH', name: '招商银行', weight: 20, lastPrice: 32.60, change: -0.35},
          {symbol: '601318.SH', name: '中国平安', weight: 18, lastPrice: 48.25, change: 0.82},
          {symbol: '000858.SZ', name: '五粮液', weight: 17, lastPrice: 172.80, change: 2.15},
          {symbol: '600900.SH', name: '长江电力', weight: 20, lastPrice: 22.45, change: 0.45}
        ]
      },
      {
        id: '2',
        name: '科技成长组合',
        description: '高成长科技企业',
        count: 8,
        createdAt: '2023-08-01',
        updatedAt: '2023-08-11',
        stocks: [
          {symbol: '300750.SZ', name: '宁德时代', weight: 30, lastPrice: 232.80, change: 3.25},
          {symbol: '002475.SZ', name: '立讯精密', weight: 15, lastPrice: 32.15, change: -1.20},
          {symbol: '603986.SH', name: '兆易创新', weight: 12.5, lastPrice: 105.60, change: 0.75}
        ]
      }
    ]);

    const selectedBasket = ref('');
    const currentBasket = ref(null);

    const handleBasketChange = (basketId) => {
      currentBasket.value = baskets.value.find(b => b.id === basketId);
      emit('basket-change', currentBasket.value);
    };

    const createNewBasket = () => {
      const newId = `basket-${Date.now()}`;
      const newBasket = {
        id: newId,
        name: `新篮子 ${baskets.value.length + 1}`,
        description: '',
        count: 0,
        createdAt: new Date().toISOString().split('T')[0],
        updatedAt: new Date().toISOString().split('T')[0],
        stocks: []
      };

      baskets.value.push(newBasket);
      selectedBasket.value = newId;
      currentBasket.value = newBasket;
      emit('basket-created', newBasket);
    };

    const updateWeight = (stock) => {
      emit('weight-updated', {
        basketId: currentBasket.value.id,
        symbol: stock.symbol,
        weight: stock.weight
      });
    };

    const removeStock = (stock) => {
      const index = currentBasket.value.stocks.findIndex(s => s.symbol === stock.symbol);
      if (index !== -1) {
        currentBasket.value.stocks.splice(index, 1);
        currentBasket.value.count = currentBasket.value.stocks.length;
        emit('stock-removed', {
          basketId: currentBasket.value.id,
          symbol: stock.symbol
        });
      }
    };

    const applyToTrade = () => {
      emit('apply-basket', currentBasket.value);
    };

    const exportBasket = () => {
      emit('export-basket', currentBasket.value);
    };

    const deleteBasket = () => {
      emit('basket-deleted', currentBasket.value.id);
      baskets.value = baskets.value.filter(b => b.id !== currentBasket.value.id);
      selectedBasket.value = '';
      currentBasket.value = null;
    };

    const handleStockClick = (stock) => {
      emit('stock-click', stock);
    };

    return {
      baskets,
      selectedBasket,
      currentBasket,
      handleBasketChange,
      createNewBasket,
      updateWeight,
      removeStock,
      applyToTrade,
      exportBasket,
      deleteBasket,
      handleStockClick
    };
  }
}
</script>

<style scoped>
.basket-selector {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.selector-header {
  margin-bottom: 20px;
  display: flex;
}

.basket-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.basket-info {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.basket-info h3 {
  margin: 0 0 10px 0;
  font-size: 18px;
}

.description {
  color: #606266;
  font-size: 14px;
  margin: 5px 0;
}

.stats {
  color: #909399;
  font-size: 12px;
  margin: 5px 0;
}

.basket-stocks {
  flex: 1;
  margin-bottom: 15px;
}

.basket-actions {
  text-align: left;
}

.empty-basket {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.up {
  color: #f56c6c;
}

.down {
  color: #5cb87a;
}
</style>