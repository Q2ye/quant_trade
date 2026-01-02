<!--K线图组件-->
<template>
  <div ref="chart" class="kline-chart">
    <div v-if="!hasData" class="empty-chart">
      <i class="fas fa-chart-line"></i>
      <p>暂无K线数据</p>
      <p class="hint">请选择交易标的查看K线图</p>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts';
import 'echarts/extension/bmap/bmap';

export default {
  name: "KLineChart",
  props: {
    symbol: {
      type: String,
      default: ''
    },
    period: {
      type: String,
      default: '5min'
    },
    data: {
      type: Array,
      default: () => []  // 提供默认空数组
    },
    indicators: {
      type: Array,
      default: () => ['MA5', 'MA10', 'VOL']
    }
  },
  data() {
    return {
      chart: null,
      hasData: false
    }
  },
  computed: {
    safeData() {
      return Array.isArray(this.data) ? this.data : [];
    }
  },
  watch: {
    symbol: {
      handler(newSymbol) {
        if (newSymbol) {
          this.loadKLineData();
        } else {
          this.clearChart();
        }
      },
      immediate: true
    },
    period() {
      if (this.symbol) {
        this.loadKLineData();
      }
    },
    safeData: {
      deep: true,
      handler(newData) {
        this.hasData = newData && newData.length > 0;
        if (this.hasData) {
          this.$nextTick(() => {
            this.updateChart();
          });
        } else {
          this.clearChart();
        }
      }
    },
    indicators() {
      if (this.hasData) {
        this.updateChart();
      }
    }
  },
  mounted() {
    this.initChart();
    window.addEventListener('resize', this.resizeHandler);
  },
  beforeUnmount() {
    // 移除事件监听器
    window.removeEventListener('resize', this.resizeHandler);

    // 安全销毁图表实例
    if (this.chart) {
      try {
        this.chart.dispose();
      } catch (error) {
        console.warn('销毁图表时出错:', error);
      }
      this.chart = null;
    }
  },
  methods: {
    initChart() {
      if (!this.$refs.chart) {
        console.warn('图表容器未找到');
        return;
      }

      const chartElement = this.$refs.chart;

      // 检查容器尺寸
      if (chartElement.clientWidth === 0 || chartElement.clientHeight === 0) {
        console.warn('图表容器尺寸为0，延迟初始化');
        // 使用更安全的延迟初始化
        setTimeout(() => {
          // 检查是否已经卸载
          if (this.$refs.chart) {
            this.initChart();
          }
        }, 300);
        return;
      }

      try {
        // 如果已有图表实例，先销毁
        if (this.chart) {
          this.chart.dispose();
        }

        this.chart = echarts.init(chartElement);
        console.log('图表初始化成功');

        // 设置默认的空配置
        const emptyOption = this.getEmptyOption();
        this.chart.setOption(emptyOption);
      } catch (error) {
        console.error('图表初始化失败:', error);
        this.chart = null;
      }
    },
    resizeHandler() {
      if (this.chart) {
        const chartElement = this.$refs.chart;
        if (chartElement && chartElement.clientWidth > 0 && chartElement.clientHeight > 0) {
          this.chart.resize();
        }
      }
    },

    async loadKLineData() {
      if (!this.symbol) {
        this.clearChart();
        return;
      }

      try {
        console.log(`加载K线数据: ${this.symbol}, 周期: ${this.period}`);

        // 模拟加载K线数据
        const mockData = this.generateMockKLineData();
        console.log('生成的K线数据长度:', mockData.length);

        // 更新内部数据状态
        this.hasData = mockData && mockData.length > 0;

        if (this.hasData) {
          // 确保图表已经初始化
          if (!this.chart) {
            this.initChart();
          }

          // 使用更可靠的方式更新图表
          this.$nextTick(() => {
            setTimeout(() => {
              this.updateChart(mockData);
            }, 100);
          });
        } else {
          this.clearChart();
        }

        this.$emit('events-loaded', mockData);
      } catch (error) {
        console.error('加载K线数据失败:', error);
        this.clearChart();
      }
    },
    generateMockKLineData() {
      if (!this.symbol) return [];

      const basePrice = this.getBasePrice(this.symbol);
      const data = [];
      const now = new Date();

      // 根据周期生成不同数量的数据点
      const dataPoints = this.getDataPointsByPeriod();

      for (let i = dataPoints; i > 0; i--) {
        const date = new Date(now);

        // 根据周期调整时间
        if (this.period === '1min') {
          date.setMinutes(date.getMinutes() - i);
        } else if (this.period === '5min') {
          date.setMinutes(date.getMinutes() - i * 5);
        } else if (this.period === 'daily') {
          date.setDate(date.getDate() - i);
        }

        // 修复：正确计算开盘价
        let open;
        if (data.length === 0) {
          open = basePrice;
        } else {
          open = data[data.length - 1].close;
        }

        const change = (Math.random() - 0.5) * basePrice * 0.02;
        const close = open + change;
        const high = Math.max(open, close) + Math.random() * basePrice * 0.01;
        const low = Math.min(open, close) - Math.random() * basePrice * 0.01;
        const volume = Math.floor(Math.random() * 10000) + 1000;

        data.push({
          date: date.toISOString().split('T')[0],
          time: date.toLocaleTimeString('zh-CN', {hour12: false}),
          open: +open.toFixed(2),
          close: +close.toFixed(2),
          high: +high.toFixed(2),
          low: +low.toFixed(2),
          volume: volume
        });
      }

      return data;
    },

    getBasePrice(symbol) {
      const priceMap = {
        '600519.SH': 1685.50,
        '601318.SH': 48.25,
        '600036.SH': 32.60,
        '000333.SZ': 55.80,
        '601888.SH': 102.40
      };
      return priceMap[symbol] || 10 + Math.random() * 100;
    },

    getDataPointsByPeriod() {
      const pointsMap = {
        '1min': 240,   // 4小时交易时间
        '5min': 48,    // 4小时交易时间
        'daily': 30    // 30个交易日
      };
      return pointsMap[this.period] || 100;
    },

    updateChart(chartData = null) {
      if (!this.chart) {
        this.initChart();
      }

      const displayData = chartData || this.safeData;

      if (!displayData || displayData.length === 0) {
        this.clearChart();
        return;
      }

      try {
        const option = this.generateOption(displayData);
        this.chart.setOption(option, true);
      } catch (error) {
        console.error('更新图表失败:', error);
      }
    },

    clearChart() {
      this.hasData = false;
      if (this.chart) {
        const emptyOption = {
          title: {
            text: '暂无数据',
            left: 'center',
            top: 'center',
            textStyle: {
              color: '#a8c7ff',
              fontSize: 16,
              fontWeight: 'normal'
            }
          }
        };
        this.chart.setOption(emptyOption, true);
      }
    },

    generateOption(displayData = null) {
      // 使用传入的数据，如果没有则使用safeData
      const dataToUse = displayData || this.safeData;

      // 检查数据是否有效
      if (!dataToUse || dataToUse.length === 0) {
        return this.getEmptyOption();
      }

      const dates = dataToUse.map(d =>
          this.period === 'daily' ? d.date : d.time
      );

      return {
        backgroundColor: 'transparent',
        animation: false, // 禁用动画避免性能问题
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          },
          backgroundColor: 'rgba(16, 33, 59, 0.95)',
          borderColor: 'rgba(64, 158, 255, 0.3)',
          borderWidth: 1,
          textStyle: {
            color: '#e0e7ff'
          },
          formatter: params => {
            const data = params[0].data;
            if (!Array.isArray(data)) return '';

            const dataIndex = params[0].dataIndex;
            const item = dataToUse[dataIndex];

            return `
          <div style="font-weight: bold; margin-bottom: 8px; color: #64b5f6;">${this.symbol}</div>
          <div>时间: ${dates[dataIndex]}</div>
          <div>开盘: ${item.open}</div>
          <div>收盘: ${item.close}</div>
          <div>最低: ${item.low}</div>
          <div>最高: ${item.high}</div>
          <div>成交量: ${item.volume?.toLocaleString() || 0}</div>
        `;
          }
        },
        legend: {
          data: ['K线', ...this.getIndicatorNames()],
          textStyle: {
            color: '#a8c7ff'
          },
          top: 10
        },
        grid: [
          {
            left: '10%',
            right: '10%',
            top: '15%',
            height: '55%'
          },
          {
            left: '10%',
            right: '10%',
            top: '75%',
            height: '15%'
          }
        ],
        xAxis: [
          {
            type: 'category',
            data: dates,
            scale: true,
            boundaryGap: false,
            axisLine: {
              lineStyle: {color: '#a8c7ff'}
            },
            axisLabel: {
              color: '#a8c7ff',
              formatter: value => {
                if (this.period === 'daily') {
                  return value.slice(5); // 显示 MM-DD
                }
                return value;
              }
            },
            splitLine: {
              show: true,
              lineStyle: {
                color: 'rgba(168, 199, 255, 0.1)'
              }
            }
          },
          {
            type: 'category',
            gridIndex: 1,
            data: dates,
            axisLabel: {show: false},
            axisLine: {show: false},
            splitLine: {show: false}
          }
        ],
        yAxis: [
          {
            scale: true,
            splitArea: {
              show: true,
              areaStyle: {
                color: ['rgba(16, 33, 59, 0.3)', 'rgba(16, 33, 59, 0.1)']
              }
            },
            axisLine: {
              lineStyle: {color: '#a8c7ff'}
            },
            axisLabel: {
              color: '#a8c7ff',
              formatter: value => value.toFixed(2)
            },
            splitLine: {
              show: true,
              lineStyle: {
                color: 'rgba(168, 199, 255, 0.1)'
              }
            }
          },
          {
            scale: true,
            gridIndex: 1,
            splitNumber: 2,
            axisLabel: {show: false},
            axisLine: {show: false},
            splitLine: {show: false}
          }
        ],
        dataZoom: [
          {
            type: 'inside',
            xAxisIndex: [0, 1],
            start: 70,
            end: 100,
            filterMode: 'filter'
          },
          {
            show: true,
            xAxisIndex: [0, 1],
            type: 'slider',
            bottom: 10,
            start: 70,
            end: 100,
            backgroundColor: 'rgba(16, 33, 59, 0.8)',
            borderColor: 'rgba(64, 158, 255, 0.3)',
            textStyle: {
              color: '#a8c7ff'
            }
          }
        ],
        series: [
          {
            name: 'K线',
            type: 'candlestick',
            data: dataToUse.map(d => [d.open, d.close, d.low, d.high]),
            itemStyle: {
              color: '#5cdd8b',
              color0: '#ff6b6b',
              borderColor: '#5cdd8b',
              borderColor0: '#ff6b6b',
              borderWidth: 1
            },
            emphasis: {
              itemStyle: {
                borderWidth: 2
              }
            }
          },
          ...this.generateIndicatorSeries(dataToUse)
        ]
      };
    },

    getIndicatorNames() {
      const names = [];
      if (this.indicators.includes('MA5')) names.push('MA5');
      if (this.indicators.includes('MA10')) names.push('MA10');
      return names;
    },

    generateIndicatorSeries(displayData = null) {
      const dataToUse = displayData || this.safeData;
      const series = [];

      if (this.indicators.includes('MA5')) {
        const ma5Data = this.calculateMA(5, dataToUse);
        series.push({
          name: 'MA5',
          type: 'line',
          data: ma5Data,
          smooth: true,
          lineStyle: {
            width: 2,
            color: '#ffb86c'
          },
          symbol: 'none'
        });
      }

      if (this.indicators.includes('MA10')) {
        const ma10Data = this.calculateMA(10, dataToUse);
        series.push({
          name: 'MA10',
          type: 'line',
          data: ma10Data,
          smooth: true,
          lineStyle: {
            width: 2,
            color: '#64b5f6'
          },
          symbol: 'none'
        });
      }

      if (this.indicators.includes('VOL')) {
        series.push({
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: dataToUse.map(d => d.volume),
          itemStyle: {
            color: params => {
              const data = dataToUse[params.dataIndex];
              return data.close >= data.open ? '#5cdd8b' : '#ff6b6b';
            },
            opacity: 0.7
          }
        });
      }

      return series;
    },

    getEmptyOption() {
      return {
        title: {
          text: '暂无数据',
          left: 'center',
          top: 'center',
          textStyle: {
            color: '#a8c7ff',
            fontSize: 16,
            fontWeight: 'normal'
          }
        }
      };
    },

    calculateMA(dayCount) {
      if (!this.safeData.length) return [];

      const result = [];
      for (let i = 0; i < this.safeData.length; i++) {
        if (i < dayCount - 1) {
          result.push('-');
          continue;
        }
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
          sum += this.safeData[i - j].close;
        }
        result.push(+(sum / dayCount).toFixed(2));
      }
      return result;
    }
  }
}
</script>

<style scoped>
.kline-chart {
  width: 100%;
  height: 100%;
  min-height: 400px; /* 确保最小高度 */
  position: relative;
}

.empty-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px; /* 与图表相同的最小高度 */
  color: #a8c7ff;
  opacity: 0.7;
}

.empty-chart i {
  font-size: 4rem;
  margin-bottom: 16px;
}

.empty-chart p {
  margin: 4px 0;
  font-size: 1.1rem;
}

.hint {
  font-size: 0.9rem !important;
  opacity: 0.6;
}
</style>