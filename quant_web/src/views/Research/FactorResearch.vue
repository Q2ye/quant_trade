<template>
  <div class="factor-research">
    <div class="page-header">
      <h1 class="page-title"><i class="fas fa-flask"></i> 因子研究</h1>
      <div class="action-buttons">
        <el-button type="primary" icon="el-icon-video-play">执行回测</el-button>
        <el-button icon="el-icon-download">导出结果</el-button>
      </div>
    </div>

    <div class="research-layout">
      <div class="factor-config-panel">
        <h3 class="panel-title"><i class="fas fa-cog"></i> 因子配置</h3>

        <div class="param-group">
          <label class="param-label">回测周期</label>
          <el-date-picker
            v-model="backtestRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            size="small"
            style="width: 100%">
          </el-date-picker>
        </div>

        <div class="param-group">
          <label class="param-label">初始资金</label>
          <el-input v-model="initialCapital" size="small" placeholder="1,000,000"></el-input>
        </div>

        <div class="param-group">
          <label class="param-label">基准指数</label>
          <el-select v-model="benchmark" placeholder="请选择" size="small" style="width: 100%">
            <el-option label="沪深300 (000300.SH)" value="000300.SH"></el-option>
            <el-option label="上证指数 (000001.SH)" value="000001.SH"></el-option>
            <el-option label="中证500 (000905.SH)" value="000905.SH"></el-option>
          </el-select>
        </div>

        <h3 class="panel-title" style="margin-top: 25px;"><i class="fas fa-layer-group"></i> 选择因子</h3>

        <div class="factor-category">
          <div class="category-title">价值因子</div>
          <div class="factor-list">
            <div v-for="factor in valueFactors" :key="factor.id"
                 class="factor-item" :class="{selected: selectedFactor === factor.id}"
                 @click="selectFactor(factor.id)">
              <div>
                <div class="factor-name">{{ factor.name }}</div>
                <div class="factor-desc">{{ factor.description }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="factor-category">
          <div class="category-title">成长因子</div>
          <div class="factor-list">
            <div v-for="factor in growthFactors" :key="factor.id"
                 class="factor-item" :class="{selected: selectedFactor === factor.id}"
                 @click="selectFactor(factor.id)">
              <div>
                <div class="factor-name">{{ factor.name }}</div>
                <div class="factor-desc">{{ factor.description }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="factor-category">
          <div class="category-title">质量因子</div>
          <div class="factor-list">
            <div v-for="factor in qualityFactors" :key="factor.id"
                 class="factor-item" :class="{selected: selectedFactor === factor.id}"
                 @click="selectFactor(factor.id)">
              <div>
                <div class="factor-name">{{ factor.name }}</div>
                <div class="factor-desc">{{ factor.description }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="research-content">
        <div class="chart-container">
          <h3 class="chart-title">因子收益分析</h3>
          <div class="chart-area" ref="factorReturnChart"></div>
        </div>

        <div class="results-grid">
          <div class="results-card">
            <h3 class="chart-title">因子绩效指标</h3>
            <table class="results-table">
              <tr>
                <th>指标</th>
                <th>数值</th>
              </tr>
              <tr>
                <td>年化收益率</td>
                <td class="positive-value">18.7%</td>
              </tr>
              <tr>
                <td>夏普比率</td>
                <td class="positive-value">1.24</td>
              </tr>
              <tr>
                <td>最大回撤</td>
                <td class="negative-value">-15.3%</td>
              </tr>
              <tr>
                <td>信息比率</td>
                <td class="positive-value">0.89</td>
              </tr>
              <tr>
                <td>胜率</td>
                <td class="positive-value">62.5%</td>
              </tr>
            </table>
          </div>

          <div class="results-card">
            <h3 class="chart-title">IC分析</h3>
            <table class="results-table">
              <tr>
                <th>指标</th>
                <th>数值</th>
              </tr>
              <tr>
                <td>IC均值</td>
                <td class="positive-value">0.087</td>
              </tr>
              <tr>
                <td>IC标准差</td>
                <td>0.152</td>
              </tr>
              <tr>
                <td>IR比率</td>
                <td class="positive-value">0.57</td>
              </tr>
              <tr>
                <td>IC>0比例</td>
                <td class="positive-value">65.2%</td>
              </tr>
              <tr>
                <td>IC衰减(1期)</td>
                <td class="negative-value">-0.42</td>
              </tr>
            </table>
          </div>
        </div>

        <div class="chart-container">
          <h3 class="chart-title">十分组收益表现</h3>
          <div class="chart-area" ref="groupReturnChart"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "FactorResearch",
  data() {
    return {
      backtestRange: [new Date('2020-01-01'), new Date('2023-08-20')],
      initialCapital: '1000000',
      benchmark: '000300.SH',
      selectedFactor: 'pe_ratio',
      valueFactors: [
        { id: 'pe_ratio', name: '市盈率(PE)', description: '市值与净利润比率' },
        { id: 'pb_ratio', name: '市净率(PB)', description: '市值与净资产比率' },
        { id: 'dividend_yield', name: '股息率', description: '年度股息与股价比率' },
        { id: 'ev_ebitda', name: 'EV/EBITDA', description: '企业价值与税息折旧摊销前利润比率' }
      ],
      growthFactors: [
        { id: 'revenue_growth', name: '营收增长率', description: '营业收入同比增长率' },
        { id: 'profit_growth', name: '利润增长率', description: '净利润同比增长率' },
        { id: 'roe_growth', name: 'ROE增长率', description: '净资产收益率变化率' }
      ],
      qualityFactors: [
        { id: 'roe', name: '净资产收益率(ROE)', description: '净利润与净资产比率' },
        { id: 'roa', name: '总资产收益率(ROA)', description: '净利润与总资产比率' },
        { id: 'profit_margin', name: '净利润率', description: '净利润与营业收入比率' },
        { id: 'asset_turnover', name: '资产周转率', description: '营业收入与总资产比率' }
      ],
      returnChart: null,
      groupChart: null
    }
  },
  mounted() {
    this.initCharts();
    this.selectFactor('pe_ratio');

    // 响应窗口调整
    window.addEventListener('resize', this.handleResize);
  },
  beforeDestroy() {
    // 清理事件监听器
    window.removeEventListener('resize', this.handleResize);

    // 销毁图表实例
    if (this.returnChart) {
      this.returnChart.dispose();
    }
    if (this.groupChart) {
      this.groupChart.dispose();
    }
  },
  methods: {
    initCharts() {
      // 初始化因子收益图表
      this.returnChart = echarts.init(this.$refs.factorReturnChart);

      // 初始化分组收益图表
      this.groupChart = echarts.init(this.$refs.groupReturnChart);
    },
    selectFactor(factorId) {
      this.selectedFactor = factorId;
      this.updateCharts();
    },
    updateCharts() {
      // 更新因子收益图表
      this.returnChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          }
        },
        legend: {
          data: ['因子收益', '基准收益'],
          textStyle: {
            color: '#fff'
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: ['2020-06', '2020-12', '2021-06', '2021-12', '2022-06', '2022-12', '2023-06'],
          axisLine: {
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#ccc'
          }
        },
        yAxis: {
          type: 'value',
          axisLine: {
            show: true,
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#ccc',
            formatter: '{value}%'
          },
          splitLine: {
            lineStyle: {
              color: '#333',
              type: 'dashed'
            }
          }
        },
        series: [
          {
            name: '因子收益',
            type: 'line',
            data: [5.2, 12.8, 18.5, 22.3, 15.7, 25.4, 31.2],
            smooth: true,
            lineStyle: {
              width: 3,
              color: '#1890ff'
            },
            itemStyle: {
              color: '#1890ff'
            }
          },
          {
            name: '基准收益',
            type: 'line',
            data: [3.5, 8.2, 12.4, 15.8, 9.3, 13.7, 18.5],
            smooth: true,
            lineStyle: {
              width: 2,
              color: '#aaa',
              type: 'dashed'
            },
            itemStyle: {
              color: '#aaa'
            }
          }
        ]
      });

      // 更新分组收益图表
      this.groupChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        legend: {
          data: ['分组1(最低)', '分组2', '分组3', '分组4', '分组5', '分组6', '分组7', '分组8', '分组9', '分组10(最高)'],
          textStyle: {
            color: '#fff'
          },
          selected: {
            '分组1(最低)': true,
            '分组10(最高)': true,
            '分组2': false,
            '分组3': false,
            '分组4': false,
            '分组5': false,
            '分组6': false,
            '分组7': false,
            '分组8': false,
            '分组9': false
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '15%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: ['1月', '3月', '6月', '12月'],
          axisLine: {
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#ccc'
          }
        },
        yAxis: {
          type: 'value',
          name: '收益率(%)',
          axisLine: {
            show: true,
            lineStyle: {
              color: '#666'
            }
          },
          axisLabel: {
            color: '#ccc',
            formatter: '{value}%'
          },
          splitLine: {
            lineStyle: {
              color: '#333',
              type: 'dashed'
            }
          }
        },
        series: [
          {
            name: '分组1(最低)',
            type: 'bar',
            data: [1.2, 2.5, 3.8, 5.2],
            itemStyle: {
              color: '#f5222d'
            }
          },
          {
            name: '分组2',
            type: 'bar',
            data: [1.8, 3.2, 4.5, 6.1]
          },
          {
            name: '分组3',
            type: 'bar',
            data: [2.2, 3.8, 5.2, 7.0]
          },
          {
            name: '分组4',
            type: 'bar',
            data: [2.8, 4.5, 6.1, 8.2]
          },
          {
            name: '分组5',
            type: 'bar',
            data: [3.2, 5.1, 7.0, 9.3]
          },
          {
            name: '分组6',
            type: 'bar',
            data: [3.8, 5.8, 7.9, 10.5]
          },
          {
            name: '分组7',
            type: 'bar',
            data: [4.2, 6.5, 8.8, 11.7]
          },
          {
            name: '分组8',
            type: 'bar',
            data: [4.8, 7.2, 9.7, 12.8]
          },
          {
            name: '分组9',
            type: 'bar',
            data: [5.2, 7.8, 10.5, 13.9]
          },
          {
            name: '分组10(最高)',
            type: 'bar',
            data: [6.2, 9.1, 12.2, 16.0],
            itemStyle: {
              color: '#52c41a'
            }
          }
        ]
      });
    },
    handleResize() {
      if (this.returnChart) {
        this.returnChart.resize();
      }
      if (this.groupChart) {
        this.groupChart.resize();
      }
    }
  }
}
</script>

<style scoped>
:root {
  --primary-bg: #141414;
  --secondary-bg: #1f1f1f;
  --accent-color: #1890ff;
  --success-color: #52c41a;
  --danger-color: #f5222d;
  --warning-color: #faad14;
  --text-primary: rgba(255, 255, 255, 0.85);
  --text-secondary: rgba(255, 255, 255, 0.65);
  --border-color: #434343;
}

.factor-research {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  background-color: var(--primary-bg);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  line-height: 1.6;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--border-color);
}

.page-title {
  font-size: 24px;
  color: var(--accent-color);
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.research-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 20px;
}

.factor-config-panel {
  background: var(--secondary-bg);
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--border-color);
  height: fit-content;
}

.panel-title {
  font-size: 16px;
  margin-bottom: 15px;
  color: var(--text-primary);
  display: flex;
  align-items: center;
}

.panel-title i {
  margin-right: 8px;
  color: var(--accent-color);
}

.factor-category {
  margin-bottom: 20px;
}

.category-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 10px;
  padding-bottom: 5px;
  border-bottom: 1px solid var(--border-color);
}

.factor-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.factor-item {
  display: flex;
  align-items: center;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.factor-item:hover {
  background-color: rgba(24, 144, 255, 0.1);
}

.factor-item.selected {
  background-color: rgba(24, 144, 255, 0.2);
  border-left: 3px solid var(--accent-color);
}

.factor-name {
  flex: 1;
  font-size: 14px;
}

.factor-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.research-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-container {
  background: var(--secondary-bg);
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--border-color);
}

.chart-title {
  font-size: 16px;
  margin-bottom: 15px;
  color: var(--text-primary);
}

.chart-area {
  height: 300px;
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.results-card {
  background: var(--secondary-bg);
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--border-color);
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}

.results-table th, .results-table td {
  padding: 8px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.results-table th {
  color: var(--text-secondary);
  font-weight: normal;
}

.positive-value {
  color: var(--success-color);
}

.negative-value {
  color: var(--danger-color);
}

.param-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 15px;
}

.param-group {
  margin-bottom: 15px;
}

.param-label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 5px;
}

.param-input {
  width: 100%;
  padding: 8px;
  background: var(--primary-bg);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .research-layout {
    grid-template-columns: 1fr;
  }

  .results-grid {
    grid-template-columns: 1fr;
  }
}
</style>