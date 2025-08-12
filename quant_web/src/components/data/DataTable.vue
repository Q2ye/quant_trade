<!--通用表格（支持虚拟滚动）-->
<script>
import { VirtualScroller } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

export default {
  name: "DataTable",
  components: {
    VirtualScroller
  },
  props: {
    columns: {
      type: Array,
      required: true
    },
    data: {
      type: Array,
      required: true
    },
    rowHeight: {
      type: Number,
      default: 48
    },
    minHeight: {
      type: String,
      default: '300px'
    },
    maxHeight: {
      type: String,
      default: '600px'
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  methods: {
    formatValue(row, column) {
      const value = row[column.prop]
      if (column.formatter) {
        return column.formatter(row, column, value)
      }
      return value
    }
  }
}
</script>

<template>
  <div class="data-table-container">
    <div class="table-header">
      <div
        v-for="col in columns"
        :key="col.prop"
        class="header-cell"
        :style="{ width: col.width || 'auto', textAlign: col.align || 'left' }">
        {{ col.label }}
      </div>
    </div>

    <div v-if="loading" class="table-loading">
      <div class="loading-content">
        <i class="el-icon-loading"></i>
        <span>加载中...</span>
      </div>
    </div>

    <VirtualScroller
      v-else
      :items="data"
      :item-height="rowHeight"
      :min-item-size="rowHeight"
      :style="{ height: `min(${minHeight}, ${maxHeight})` }"
      class="virtual-scroller"
    >
      <template v-slot="{ item: row, index }">
        <div
          class="table-row"
          :class="{ 'striped-row': index % 2 === 0 }"
          :style="{ height: `${rowHeight}px` }">
          <div
            v-for="col in columns"
            :key="col.prop"
            class="body-cell"
            :style="{
              width: col.width || 'auto',
              textAlign: col.align || 'left',
              color: col.color ? col.color(row) : 'inherit'
            }">
            <slot v-if="col.slot" :name="col.slot" :row="row" :index="index" />
            <template v-else>
              {{ formatValue(row, col) }}
            </template>
          </div>
        </div>
      </template>
    </VirtualScroller>

    <div v-if="!loading && data.length === 0" class="table-empty">
      <div class="empty-content">
        <i class="el-icon-warning-outline"></i>
        <span>暂无数据</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-table-container {
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}

.table-header {
  display: flex;
  background-color: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  font-weight: bold;
  color: #606266;
}

.header-cell {
  padding: 12px 10px;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.virtual-scroller {
  width: 100%;
  overflow-y: auto;
}

.table-row {
  display: flex;
  border-bottom: 1px solid #ebeef5;
}

.striped-row {
  background-color: #fafafa;
}

.table-row:hover {
  background-color: #f5f7fa;
}

.body-cell {
  padding: 0 10px;
  display: flex;
  align-items: center;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-loading,
.table-empty {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.loading-content,
.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-content i {
  font-size: 24px;
  margin-bottom: 10px;
  animation: rotating 2s linear infinite;
}

.empty-content i {
  font-size: 24px;
  margin-bottom: 10px;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>