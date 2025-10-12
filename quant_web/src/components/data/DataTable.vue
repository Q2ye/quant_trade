<!-- quant_web/src/components/common/DataTable.vue -->
<script setup lang="ts">
import {computed} from 'vue'

/**
 * 通用表格组件 - 优化版本
 * 支持虚拟滚动、自定义列渲染、加载状态等
 */

interface TableColumn {
  prop: string
  label: string
  width?: string
  align?: 'left' | 'center' | 'right'
  formatter?: (row: any, column: TableColumn, value: any) => any
  color?: (row: any) => string
  slot?: string
}

interface Props {
  columns: TableColumn[]
  data: any[]
  rowHeight?: number
  minHeight?: string
  maxHeight?: string
  loading?: boolean
  emptyText?: string
  clickable?: boolean  // 添加点击属性控制
}

const props = withDefaults(defineProps<Props>(), {
  rowHeight: 48,
  minHeight: '300px',
  maxHeight: '600px',
  loading: false,
  emptyText: '暂无数据',
  clickable: false  // 默认不可点击
})

const emit = defineEmits<{
  rowClick: [row: any, index: number]
}>()

/**
 * 格式化单元格值
 */
const formatValue = (row: any, column: TableColumn) => {
  const value = row[column.prop]
  if (column.formatter) {
    return column.formatter(row, column, value)
  }
  return value
}

/**
 * 处理行点击事件
 */
const handleRowClick = (row: any, index: number) => {
  emit('rowClick', row, index)
}

/**
 * 计算表格高度
 */
const tableHeight = computed(() => {
  return `min(${props.minHeight}, ${props.maxHeight})`
})
</script>

<template>
  <div class="data-table-container">
    <!-- 表格头部 -->
    <div class="table-header">
      <div
          v-for="col in columns"
          :key="col.prop"
          class="header-cell"
          :style="{
          width: col.width || 'auto',
          textAlign: col.align || 'left'
        }"
      >
        {{ col.label }}
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="table-loading">
      <div class="loading-content">
        <a-spin size="large"/>
        <span class="loading-text">加载中...</span>
      </div>
    </div>

    <!-- 表格内容 - 使用虚拟滚动 -->
    <div
        v-else-if="data.length > 0"
        class="table-body"
        :style="{ height: tableHeight }"
    >
      <div
          v-for="(row, index) in data"
          :key="index"
          class="table-row"
          :class="{
          'striped-row': index % 2 === 0,
          'clickable': clickable  // 使用 prop 控制点击样式
        }"
          :style="{ height: `${rowHeight}px` }"
          @click="clickable ? handleRowClick(row, index) : null"
      >
      <div
          v-for="col in columns"
          :key="col.prop"
          class="body-cell"
          :style="{
            width: col.width || 'auto',
            textAlign: col.align || 'left',
            color: col.color ? col.color(row) : 'inherit'
          }"
      >
        <!-- 插槽支持 -->
        <slot
            v-if="col.slot"
            :name="col.slot"
            :row="row"
            :index="index"
            :column="col"
        />
        <template v-else>
          {{ formatValue(row, col) }}
        </template>
      </div>
    </div>
  </div>

  <!-- 空状态 -->
  <div v-else class="table-empty">
    <div class="empty-content">
      <a-empty :description="emptyText"/>
    </div>
  </div>
  </div>
</template>

<style scoped lang="less">
.data-table-container {
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
  background-color: #fff;
}

.table-header {
  display: flex;
  background-color: #fafafa;
  border-bottom: 1px solid #d9d9d9;
  font-weight: 600;
  color: #000000d9;
  position: sticky;
  top: 0;
  z-index: 1;
}

.header-cell {
  padding: 12px 8px;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-right: 1px solid #f0f0f0;

  &:last-child {
    border-right: none;
  }
}

.table-body {
  overflow-y: auto;
  overflow-x: hidden;
}

.table-row {
  display: flex;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.3s;

  &:last-child {
    border-bottom: none;
  }

  &.striped-row {
    background-color: #fafafa;
  }

  &.clickable {
    cursor: pointer;

    &:hover {
      background-color: #f5f5f5;
    }
  }
}

.body-cell {
  padding: 0 8px;
  display: flex;
  align-items: center;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-right: 1px solid #f0f0f0;

  &:last-child {
    border-right: none;
  }
}

.table-loading,
.table-empty {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #00000073;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;

  .loading-text {
    font-size: 14px;
  }
}

.empty-content {
  width: 100%;
}

// 响应式设计
@media (max-width: 768px) {
  .data-table-container {
    font-size: 12px;
  }

  .header-cell,
  .body-cell {
    padding: 8px 4px;
  }
}
</style>