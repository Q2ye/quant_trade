<template>
  <div class="recent-trades">
    <el-table :data="trades" height="250" style="width: 100%">
      <el-table-column prop="time" label="时间" width="90"></el-table-column>
      <el-table-column prop="symbol" label="代码" width="80"></el-table-column>
      <el-table-column prop="name" label="名称" width="100"></el-table-column>
      <el-table-column label="方向">
        <template #default="{ row }">
          <span :class="row.direction === '买入' ? 'buy' : 'sell'">
            {{ row.direction }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="price" label="价格" width="80">
        <template #default="{ row }">
          {{ row.price.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="70"></el-table-column>
      <el-table-column label="金额">
        <template #default="{ row }">
          {{ (row.price * row.quantity).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column label="状态">
        <template #default>
          <el-tag size="small" type="success">已完成</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

export default defineComponent({
  name: "RecentTrades",
  props: {
    trades: Array
  }
});
</script>

<style scoped>
.recent-trades {
  height: 100%;
}

.buy {
  color: #f56c6c;
  font-weight: bold;
}

.sell {
  color: #5cb87a;
  font-weight: bold;
}
</style>