<template>
  <div class="signal-table">
    <div class="toolbar">
      <el-input
          v-model="searchText"
          placeholder="搜索股票代码/名称"
          clearable
          size="small"
          style="width: 200px; margin-right: 10px;"
      >
        <template #prefix>
          <i class="el-icon-search"></i>
        </template>
      </el-input>

      <el-select
          v-model="filterStatus"
          placeholder="信号状态"
          clearable
          size="small"
          style="width: 120px; margin-right: 10px;"
      >
        <el-option label="待交易" value="PENDING"></el-option>
        <el-option label="已确认" value="CONFIRMED"></el-option>
        <el-option label="已过期" value="EXPIRED"></el-option>
      </el-select>

      <el-select
          v-model="filterDirection"
          placeholder="交易方向"
          clearable
          size="small"
          style="width: 100px;"
      >
        <el-option label="买入" value="BUY"></el-option>
        <el-option label="卖出" value="SELL"></el-option>
      </el-select>

      <el-button
          type="danger"
          size="small"
          style="float: right;"
          @click="clearExpired"
      >
        清除过期信号
      </el-button>
    </div>

    <el-table
        :data="filteredSignals"
        height="500"
        stripe
        highlight-current-row
        @row-click="handleRowClick"
    >
      <el-table-column prop="symbol" label="代码" width="80"></el-table-column>
      <el-table-column prop="name" label="名称" width="120"></el-table-column>
      <el-table-column label="方向" width="80">
        <template #default="{ row }">
          <span :class="row.direction === 'BUY' ? 'buy' : 'sell'">
            {{ row.direction === 'BUY' ? '买入' : '卖出' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="信号强度" width="100">
        <template #default="{ row }">
          <el-progress
              :percentage="row.strength"
              :color="getStrengthColor(row.strength)"
              :show-text="false"
          ></el-progress>
          <span class="strength-value">{{ row.strength }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="price" label="触发价格" width="100">
        <template #default="{ row }">
          {{ row.price.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="triggerTime" label="触发时间" width="160"></el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag
              :type="getStatusTagType(row.status)"
              size="small"
          >
           {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
              v-if="row.status === 'PENDING'"
              type="primary"
              size="small"
              @click.stop="confirmTrade(row)"
          >
            交易
          </el-button>
          <el-button
              v-if="row.status === 'PENDING'"
              type="danger"
              size="small"
              @click.stop="dismissSignal(row)"
          >
            忽略
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
          background
          layout="prev, pager, next"
          :total="totalSignals"
          :page-size="pageSize"
          v-model:current-page="currentPage"
      ></el-pagination>
    </div>
  </div>
</template>

<script>
import {ref, computed} from 'vue';

export default {
  name: "SignalTable",
  props: {
    signals: {
      type: Array,
      default: () => []
    }
  },

  setup(props, {emit}) {
    const searchText = ref('');
    const filterStatus = ref('');
    const filterDirection = ref('');
    const currentPage = ref(1);
    const pageSize = ref(15);

    // 示例信号数据
    const demoSignals = [
      {
        id: 1, symbol: '600519.SH', name: '贵州茅台', direction: 'BUY',
        strength: 92, price: 1850.50, triggerTime: '2023-08-12 10:15:23', status: 'PENDING',
        lastPrice: 1850.50,
        change: 1.25
      },
      {
        id: 2, symbol: '000858.SZ', name: '五粮液', direction: 'BUY',
        strength: 85, price: 172.80, triggerTime: '2023-08-12 09:42:11', status: 'PENDING',
        lastPrice: 172.80,
        change: 2.15
      },
      {
        id: 3, symbol: '601318.SH', name: '中国平安', direction: 'SELL',
        strength: 78, price: 48.25, triggerTime: '2023-08-11 14:28:45', status: 'CONFIRMED',
        lastPrice: 48.25,
        change: -0.82
      },
      {
        id: 4, symbol: '600036.SH', name: '招商银行', direction: 'BUY',
        strength: 65, price: 32.60, triggerTime: '2023-08-11 11:15:30', status: 'EXPIRED',
        lastPrice: 32.60,
        change: -0.35
      },
      {
        id: 5, symbol: '300750.SZ', name: '宁德时代', direction: 'BUY',
        strength: 88, price: 232.80, triggerTime: '2023-08-10 13:45:22', status: 'PENDING',
        lastPrice: 232.80,
        change: 3.25
      }
    ];

    const signalsData = ref([...demoSignals, ...props.signals]);

    const filteredList = computed(() => {
      return signalsData.value.filter(signal => {
        const matchesSearch = !searchText.value ||
          signal.symbol.includes(searchText.value) ||
          signal.name.includes(searchText.value);

        const matchesStatus = !filterStatus.value ||
          signal.status === filterStatus.value;

        const matchesDirection = !filterDirection.value ||
          signal.direction === filterDirection.value;

        return matchesSearch && matchesStatus && matchesDirection;
      });
    });

    const filteredSignals = computed(() => {
      return filteredList.value.slice(
        (currentPage.value - 1) * pageSize.value,
        currentPage.value * pageSize.value
      );
    });

    const totalSignals = computed(() => filteredList.value.length);

    const getStrengthColor = (strength) => {
      if (strength > 90) return '#f56c6c';
      if (strength > 80) return '#e6a23c';
      if (strength > 70) return '#5cb87a';
      return '#909399';
    };

    const getStatusTagType = (status) => {
      switch (status) {
        case 'PENDING':
          return 'warning';
        case 'CONFIRMED':
          return 'success';
        case 'EXPIRED':
          return 'info';
        default:
          return 'danger';
      }
    };

    const getStatusText = (status) => {
      switch (status) {
        case 'PENDING':
          return '待交易';
        case 'CONFIRMED':
          return '已确认';
        case 'EXPIRED':
          return '已过期';
        default:
          return status;
      }
    };

    const handleRowClick = (row) => {
      emit('row-click', row);
    };

    const confirmTrade = (signal) => {
      emit('trade', signal);
    };

    const dismissSignal = (signal) => {
      const index = signalsData.value.findIndex(s => s.id === signal.id);
      if (index !== -1) {
        signalsData.value[index].status = 'EXPIRED';
        emit('dismiss', signal);
      }
    };

    const clearExpired = () => {
      signalsData.value = signalsData.value.filter(signal => signal.status !== 'EXPIRED');
      emit('clear-expired');
    };

    return {
      searchText,
      filterStatus,
      filterDirection,
      currentPage,
      pageSize,
      filteredSignals,
      totalSignals,
      getStrengthColor,
      getStatusTagType,
      getStatusText,
      handleRowClick,
      confirmTrade,
      dismissSignal,
      clearExpired
    };
  }
}
</script>

<style scoped>
.signal-table {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  margin-bottom: 15px;
  display: flex;
}

.buy {
  color: #f56c6c;
  font-weight: bold;
}

.sell {
  color: #5cb87a;
  font-weight: bold;
}

.strength-value {
  font-size: 12px;
  color: #606266;
}

.pagination {
  margin-top: 15px;
  display: flex;
  justify-content: center;
}
</style>