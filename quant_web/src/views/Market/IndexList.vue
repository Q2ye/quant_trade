<script setup lang="ts">
// Vue相关导入
import {h, onMounted, onUnmounted, reactive, ref} from 'vue'
// 路由相关
import {useRouter} from 'vue-router'
// Ant Design Vue组件
import {Button, message, Space, Tag} from 'ant-design-vue'
// 表格列类型定义
import type {ColumnsType} from 'ant-design-vue/es/table'
// 图标组件
import {ArrowLeftOutlined, FallOutlined, LineChartOutlined, RiseOutlined} from '@ant-design/icons-vue'

// 获取路由实例
const router = useRouter()

// 返回按钮处理函数 - 修复路由问题
const handleBack = () => {
  // 使用更安全的路由返回方式
  if (window.history.length > 1) {
    router.go(-1)  // 返回上一页
  } else {
    // 如果没有历史记录，跳转到首页
    router.push('/')
  }
}

// 指数数据接口定义
interface Index {
  ts_code: string          // 指数代码
  name: string             // 指数简称
  fullname: string         // 指数全称
  market: string           // 市场
  publisher: string        // 发布方
  category: string         // 分类
  base_date: string        // 基期日期
  base_point: number       // 基期点数
  current_point: number    // 当前点数
  change: number           // 涨跌点数
  change_percent: number   // 涨跌幅
  volume: number           // 成交量
  amount: number           // 成交额
}

// 加载状态
const loading = ref(false)
// 指数列表数据
const indexList = ref<Index[]>([])
// 分页配置
const pagination = reactive({
  current: 1,      // 当前页码
  pageSize: 20,    // 每页大小
  total: 0         // 总条数
})

// 表格列定义
const columns: ColumnsType<Index> = [
  {
    title: '指数代码',      // 列标题
    dataIndex: 'ts_code',   // 数据字段
    key: 'ts_code',         // 唯一键
    width: 120              // 列宽
  },
  {
    title: '指数名称',
    dataIndex: 'name',
    key: 'name',
    width: 150
  },
  {
    title: '当前点位',
    dataIndex: 'current_point',
    key: 'current_point',
    width: 120,
    // 自定义渲染函数 - 格式化显示点数
    customRender: ({text: point}) => point ? point.toFixed(2) : '-'
  },
  {
    title: '涨跌',
    dataIndex: 'change',
    key: 'change',
    width: 100,
    // 自定义渲染函数 - 显示涨跌图标和颜色
    customRender: ({text: change}) => {
      if (change === undefined || change === null) return '-'
      // 根据涨跌选择图标
      const icon = change >= 0 ?
          h(RiseOutlined, {style: {color: '#f5222d'}}) :
          h(FallOutlined, {style: {color: '#52c41a'}})
      const color = change >= 0 ? '#f5222d' : '#52c41a'  // 红色上涨，绿色下跌
      return h('span', {style: {color, alignItems: 'center', gap: '4px'}}, [
        icon,
        change >= 0 ? '+' : '',  // 正数显示+号
        change.toFixed(2)        // 保留两位小数
      ])
    }
  },
  {
    title: '涨跌幅',
    dataIndex: 'change_percent',
    key: 'change_percent',
    width: 100,
    // 自定义渲染函数 - 格式化百分比显示
    customRender: ({text: percent}) => {
      if (percent === undefined || percent === null) return '-'
      const color = percent >= 0 ? '#f5222d' : '#52c41a'
      return h('span', {style: {color}}, [
        percent >= 0 ? '+' : '',
        percent.toFixed(2),  // 保留两位小数
        '%'                  // 百分比符号
      ])
    }
  },
  {
    title: '成交量(亿)',
    dataIndex: 'volume',
    key: 'volume',
    width: 120,
    // 自定义渲染函数 - 转换为亿单位
    customRender: ({text: volume}) => {
      if (!volume) return '-'
      return (volume / 100000000).toFixed(2)  // 除以1亿
    }
  },
  {
    title: '成交额(亿)',
    dataIndex: 'amount',
    key: 'amount',
    width: 120,
    // 自定义渲染函数 - 转换为亿单位
    customRender: ({text: amount}) => {
      if (!amount) return '-'
      return (amount / 100000000).toFixed(2)  // 除以1亿
    }
  },
  {
    title: '市场',
    dataIndex: 'market',
    key: 'market',
    width: 80,
    // 自定义渲染函数 - 使用标签显示市场
    customRender: ({text: market}) => {
      if (!market) return '-'
      return h(Tag, {color: 'blue'}, () => market)  // 蓝色标签
    }
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    width: 100
  },
  {
    title: '操作',      // 操作列
    key: 'actions',     // 操作列唯一键
    width: 100,
    // 自定义渲染函数 - 操作按钮
    customRender: ({record}) => h(Space, {size: 'small'}, () => [
      h(Button, {
        type: 'link',     // 链接样式按钮
        size: 'small',    // 小尺寸
        icon: h(LineChartOutlined),  // 图表图标
        onClick: () => viewIndexDetail(record)  // 点击事件
      }, () => '详情')    // 按钮文字
    ])
  }
]

// 加载指数列表数据
const loadIndexList = async () => {
  loading.value = true  // 开始加载
  try {
    // 模拟API请求延迟
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 模拟数据
    const mockData: Index[] = [
      {
        ts_code: '000001.SH',
        name: '上证指数',
        fullname: '上海证券综合指数',
        market: '上证',
        publisher: '上海证券交易所',
        category: '综合指数',
        base_date: '1990-12-19',
        base_point: 100,
        current_point: 3200.45,
        change: 25.67,
        change_percent: 0.81,
        volume: 450000000,
        amount: 3800.25
      },
      {
        ts_code: '399001.SZ',
        name: '深证成指',
        fullname: '深圳成份指数',
        market: '深证',
        publisher: '深圳证券交易所',
        category: '成份指数',
        base_date: '1994-07-20',
        base_point: 1000,
        current_point: 11500.78,
        change: -15.23,
        change_percent: -0.13,
        volume: 320000000,
        amount: 2800.67
      }
    ]

    // 设置数据
    indexList.value = mockData
    pagination.total = mockData.length

  } catch (error) {
    console.error('加载指数列表失败:', error)
    message.error('加载指数列表失败')  // 错误提示
    // 确保即使出错也设置空数组
    indexList.value = []
    pagination.total = 0
  } finally {
    loading.value = false  // 结束加载
  }
}

// 查看指数详情
const viewIndexDetail = (index: Index) => {
  // 使用router.push跳转到详情页
  router.push(`/market/index/${index.ts_code}`)
}

// 组件挂载时加载数据
onMounted(() => {
  loadIndexList()
})

// 组件卸载时清理数据
onUnmounted(() => {
  indexList.value = []  // 清空数据防止内存泄漏
})
</script>

<template>
  <!-- 指数列表页面容器 -->
  <div class="index-list-page">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <!-- 标题部分 -->
        <div class="title-section">
          <h1 class="page-title">指数行情</h1>
          <p class="page-description">主要市场指数表现与趋势分析</p>
        </div>
        <!-- 操作按钮区域 -->
        <div class="header-actions-right">
          <!-- 返回按钮 -->
          <a-button class="back-btn" @click="handleBack" :disabled="loading">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>

    <!-- 指数列表卡片 -->
    <a-card
        class="index-list-card"
        title="指数列表"
        :bordered="false"
    >
      <!-- 表格组件
      // 列配置
      // 数据源
      // 分页配置
      // 加载状态
      // 行唯一键
      // 横向滚动
       -->
      <a-table
          class="index-table"
          :columns="columns"
          :data-source="indexList"
          :pagination="pagination"
          :loading="loading"
          row-key="ts_code"
          :scroll="{ x: 1000 }"
      >
        <!-- 表头单元格插槽 -->
        <template #headerCell="{ column }">
          <span class="table-header">{{ column.title }}</span>
        </template>

        <!-- 表格单元格插槽 -->
        <template #bodyCell="{ column, record }">
          <!-- 指数名称列特殊处理 -->
          <template v-if="column.key === 'name'">
            <div class="index-name-cell">
              <div class="index-name">{{ record.name }}</div>
              <div class="index-fullname">{{ record.fullname }}</div>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<style scoped lang="scss">
// SCSS变量和混合导入
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';

// 页面容器样式
.index-list-page {
  .main-content {
    @include mixin.content-with-sidebar;  // 使用侧边栏内容布局
    margin: 0 auto;
  }
}

// 页面头部样式
.page-header {
  @include mixin.page-header-base;        // 使用基础页面头部样式
  margin-bottom: map.get($spacers, 6);    // 底部间距
}

// 指数列表卡片样式
.index-list-card {
  @include mixin.card-base;               // 使用基础卡片样式
  padding: map.get($spacers, 4);          // 内边距

  // 深度选择器修改卡片头部样式
  :deep(.ant-card-head) {
    @include mixin.card-header-base;      // 使用基础卡片头部样式
    border-bottom: $border-width solid $border-color;  // 底部边框
  }
}

// 返回按钮样式
.back-btn {
  @include mixin.button-base(rgba(255, 255, 255, 0.15), white);  // 半透明背景，白色文字
  border: 1px solid rgba(255, 255, 255, 0.3);  // 半透明边框
  backdrop-filter: blur(10px);            // 背景模糊效果

  // 悬停状态
  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.25);  // 提高背景透明度
    border-color: rgba(255, 255, 255, 0.5); // 提高边框透明度
  }
}
// ============================================================================
// 表格样式系统 - 使用统一的表格基础样式
// ============================================================================
.index-table {
  @include mixin.table-base-styles;
}
</style>