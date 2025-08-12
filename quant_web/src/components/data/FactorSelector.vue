<!--因子选择器-->
<script>
export default {
  name: "FactorSelector",
  props: {
    factors: {
      type: Array,
      default: () => [
        { id: 'pe', name: '市盈率(PE)', category: '估值' },
        { id: 'pb', name: '市净率(PB)', category: '估值' },
        { id: 'roe', name: '净资产收益率(ROE)', category: '盈利能力' },
        { id: 'rev_growth', name: '营收增长率', category: '成长能力' },
        { id: 'debt_ratio', name: '资产负债率', category: '偿债能力' },
        { id: 'beta', name: '贝塔系数', category: '风险指标' },
        { id: 'rsi', name: '相对强弱指数(RSI)', category: '技术指标' },
        { id: 'macd', name: 'MACD指标', category: '技术指标' }
      ]
    },
    selected: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      localSelected: [...this.selected],
      searchText: '',
      categoryFilter: 'all',
      categories: ['all', '估值', '盈利能力', '成长能力', '偿债能力', '风险指标', '技术指标']
    }
  },
  computed: {
    filteredFactors() {
      return this.factors.filter(factor => {
        const matchesSearch = factor.name.toLowerCase().includes(this.searchText.toLowerCase())
        const matchesCategory = this.categoryFilter === 'all' || factor.category === this.categoryFilter
        return matchesSearch && matchesCategory
      })
    },

    groupedFactors() {
      const groups = {}
      this.filteredFactors.forEach(factor => {
        if (!groups[factor.category]) {
          groups[factor.category] = []
        }
        groups[factor.category].push(factor)
      })
      return groups
    }
  },
  watch: {
    selected(newVal) {
      this.localSelected = [...newVal]
    }
  },
  methods: {
    toggleFactor(factorId) {
      const index = this.localSelected.indexOf(factorId)
      if (index === -1) {
        this.localSelected.push(factorId)
      } else {
        this.localSelected.splice(index, 1)
      }
      this.emitChange()
    },

    clearSelection() {
      this.localSelected = []
      this.emitChange()
    },

    emitChange() {
      this.$emit('update:selected', [...this.localSelected])
      this.$emit('change', [...this.localSelected])
    }
  }
}
</script>

<template>
  <div class="factor-selector">
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        placeholder="搜索因子..."
        prefix-icon="el-icon-search"
        size="small"
        clearable
      />

      <el-select
        v-model="categoryFilter"
        placeholder="全部分类"
        size="small"
        class="category-select">
        <el-option
          v-for="category in categories"
          :key="category"
          :label="category === 'all' ? '全部分类' : category"
          :value="category"
        />
      </el-select>

      <el-button
        size="small"
        type="text"
        @click="clearSelection">
        清空已选
      </el-button>
    </div>

    <div class="selected-factors" v-if="localSelected.length > 0">
      <div class="selected-title">已选因子 ({{ localSelected.length }})</div>
      <div class="selected-list">
        <el-tag
          v-for="id in localSelected"
          :key="id"
          closable
          size="small"
          @close="toggleFactor(id)">
          {{ factors.find(f => f.id === id).name }}
        </el-tag>
      </div>
    </div>

    <div class="factor-groups">
      <div
        v-for="(group, category) in groupedFactors"
        :key="category"
        class="factor-group">
        <div class="group-title">{{ category }}</div>
        <div class="group-items">
          <div
            v-for="factor in group"
            :key="factor.id"
            class="factor-item"
            :class="{ selected: localSelected.includes(factor.id) }"
            @click="toggleFactor(factor.id)">
            <div class="factor-name">{{ factor.name }}</div>
            <div class="factor-id">{{ factor.id }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.factor-selector {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
  background-color: #fff;
}

.filter-bar {
  display: flex;
  margin-bottom: 15px;
  gap: 10px;
}

.filter-bar .el-input {
  flex: 1;
}

.category-select {
  width: 120px;
}

.selected-factors {
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.selected-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.selected-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.factor-groups {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 5px;
}

.factor-group {
  margin-bottom: 20px;
}

.group-title {
  font-weight: bold;
  color: #606266;
  padding: 5px 0;
  border-bottom: 1px dashed #ebeef5;
  margin-bottom: 10px;
}

.group-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.factor-item {
  padding: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  background-color: #fafafa;
}

.factor-item:hover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.factor-item.selected {
  border-color: #409eff;
  background-color: #d9ecff;
}

.factor-name {
  font-size: 13px;
  margin-bottom: 3px;
}

.factor-id {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}
</style>