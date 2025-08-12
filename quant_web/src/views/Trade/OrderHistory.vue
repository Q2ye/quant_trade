<!--订单记录-->
<template>
  <div class="order-history">
    <el-card>
      <div slot="header" class="clearfix">
        <span>历史订单</span>
        <div style="float: right;">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            size="mini"
            style="width: 280px; margin-right: 10px;"
          />
          <el-button
            type="primary"
            size="mini"
            icon="el-icon-search"
            @click="searchOrders">
            查询
          </el-button>
        </div>
      </div>

      <el-table :data="filteredOrders" style="width: 100%" height="550">
        <el-table-column prop="orderId" label="委托号" width="180" />
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="direction" label="方向" width="80">
          <template slot-scope="scope">
            <span :style="{color: scope.row.direction === '买入' ? '#f56c6c' : '#67c23a'}">
              {{ scope.row.direction }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="委托价" width="120" align="right">
          <template slot-scope="scope">
            {{ scope.row.price.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="100" align="right" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template slot-scope="scope">
            {{ (scope.row.price * scope.row.quantity).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template slot-scope="scope">
            <el-tag :type="getStatusType(scope.row.status)" size="small">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="orderTime" label="委托时间" width="180" />
        <el-table-column prop="tradeTime" label="成交时间" width="180" />
        <el-table-column prop="tradePrice" label="成交价" width="120" align="right">
          <template slot-scope="scope">
            <span v-if="scope.row.status === '已成'">
              {{ scope.row.tradePrice.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="totalOrders"
          :page-size="pageSize"
          :current-page="currentPage"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: "OrderHistory",
  data() {
    return {
      dateRange: [new Date(Date.now() - 30 * 24 * 3600 * 1000), new Date()],
      orders: [],
      filteredOrders: [],
      currentPage: 1,
      pageSize: 20,
      totalOrders: 0
    }
  },
  mounted() {
    this.fetchOrders();
  },
  methods: {
    fetchOrders() {
      // 模拟数据
      this.orders = [
        {
          orderId: '202308090001',
          symbol: '600519.SH',
          name: '贵州茅台',
          direction: '买入',
          price: 1850.00,
          quantity: 100,
          status: '已成',
          orderTime: '2023-08-09 10:05:32',
          tradeTime: '2023-08-09 10:05:35',
          tradePrice: 1850.50
        },
        {
          orderId: '202308080002',
          symbol: '000001.SH',
          name: '上证指数',
          direction: '卖出',
          price: 3240.00,
          quantity: 200,
          status: '已成',
          orderTime: '2023-08-08 09:45:18',
          tradeTime: '2023-08-08 09:45:20',
          tradePrice: 3245.67
        },
        {
          orderId: '202308070003',
          symbol: '300750.SZ',
          name: '宁德时代',
          direction: '买入',
          price: 230.00,
          quantity: 300,
          status: '部分成交',
          orderTime: '2023-08-07 13:25:45',
          tradeTime: '2023-08-07 13:26:10',
          tradePrice: 230.50
        }
      ];

      this.filteredOrders = this.orders;
      this.totalOrders = this.orders.length;
    },
    searchOrders() {
      // 实际项目中根据日期范围查询订单
      this.$message.success('查询成功');
    },
    getStatusType(status) {
      const map = {
        '已报': 'info',
        '已成': 'success',
        '部分成交': 'warning',
        '已撤': '',
        '废单': 'danger'
      };
      return map[status] || '';
    },
    handleSizeChange(size) {
      this.pageSize = size;
      this.currentPage = 1;
      this.filterOrders();
    },
    handlePageChange(page) {
      this.currentPage = page;
      this.filterOrders();
    },
    filterOrders() {
      // 实际项目中根据分页过滤数据
      const start = (this.currentPage - 1) * this.pageSize;
      const end = start + this.pageSize;
      this.filteredOrders = this.orders.slice(start, end);
    }
  }
}
</script>

<style scoped>
.order-history {
  padding: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}
</style>