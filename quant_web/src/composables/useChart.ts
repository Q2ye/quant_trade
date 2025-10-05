// 图表初始化和更新逻辑
import { ref, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { EChartsType } from 'echarts'

interface ChartConfig {
  theme?: string
  renderer?: 'canvas' | 'svg'
  devicePixelRatio?: number
}

export function useChart() {
  const chartInstance = ref<EChartsType | null>(null)
  const chartContainer = ref<HTMLElement | null>(null)

  // 初始化图表
  const initChart = (container: HTMLElement, config?: ChartConfig) => {
    if (!container) {
      console.error('图表容器不能为空')
      return
    }

    chartContainer.value = container
    chartInstance.value = echarts.init(container, config?.theme, {
      renderer: config?.renderer || 'canvas',
      devicePixelRatio: config?.devicePixelRatio || window.devicePixelRatio
    })

    // 响应式调整
    const resizeObserver = new ResizeObserver(() => {
      resizeChart()
    })
    resizeObserver.observe(container)

    return chartInstance.value
  }

  // 设置图表选项
  const setChartOption = (option: echarts.EChartsOption, notMerge?: boolean, lazyUpdate?: boolean) => {
    if (chartInstance.value) {
      chartInstance.value.setOption(option, notMerge, lazyUpdate)
    }
  }

  // 调整图表大小
  const resizeChart = (width?: number, height?: number) => {
    if (chartInstance.value) {
      nextTick(() => {
        chartInstance.value!.resize({
          width: width || 'auto',
          height: height || 'auto'
        })
      })
    }
  }

  // 显示加载动画
  const showLoading = (type?: string, options?: echarts.EChartsLoadingOption) => {
    if (chartInstance.value) {
      chartInstance.value.showLoading(type, options)
    }
  }

  // 隐藏加载动画
  const hideLoading = () => {
    if (chartInstance.value) {
      chartInstance.value.hideLoading()
    }
  }

  // 获取图表实例
  const getInstance = () => {
    return chartInstance.value
  }

  // 销毁图表
  const disposeChart = () => {
    if (chartInstance.value) {
      chartInstance.value.dispose()
      chartInstance.value = null
    }
  }

  // K线图配置生成器
  const generateKLineOption = (data: any[], config?: any): echarts.EChartsOption => {
    return {
      backgroundColor: '#1a1a1a',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        data: ['K线', 'MA5', 'MA10', 'MA20'],
        textStyle: {
          color: '#ccc'
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        },
        backgroundColor: 'rgba(0,0,0,0.8)',
        borderWidth: 0,
        textStyle: {
          color: '#fff'
        }
      },
      grid: [
        {
          left: '10%',
          right: '10%',
          top: '50px',
          height: '50%'
        },
        {
          left: '10%',
          right: '10%',
          top: '65%',
          height: '15%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: data.map(item => item.date),
          scale: true,
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          splitNumber: 20,
          axisLabel: {
            color: '#ccc'
          }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: data.map(item => item.date),
          axisLabel: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          splitArea: {
            show: true
          },
          axisLabel: {
            color: '#ccc'
          }
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: true },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 80,
          end: 100
        }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: data.map(item => [item.open, item.close, item.low, item.high]),
          itemStyle: {
            color: '#ef232a',
            color0: '#14b143',
            borderColor: '#ef232a',
            borderColor0: '#14b143'
          }
        },
        {
          name: 'MA5',
          type: 'line',
          data: calculateMA(5, data),
          smooth: true,
          lineStyle: {
            opacity: 0.8,
            width: 1
          }
        },
        {
          name: 'MA10',
          type: 'line',
          data: calculateMA(10, data),
          smooth: true,
          lineStyle: {
            opacity: 0.8,
            width: 1
          }
        },
        {
          name: 'MA20',
          type: 'line',
          data: calculateMA(20, data),
          smooth: true,
          lineStyle: {
            opacity: 0.8,
            width: 1
          }
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: data.map(item => item.volume),
          itemStyle: {
            color: (params: any) => {
              const data = params.data
              const item = data[params.dataIndex]
              return item.close >= item.open ? '#ef232a' : '#14b143'
            }
          }
        }
      ]
    }
  }

  // 计算移动平均线
  const calculateMA = (dayCount: number, data: any[]) => {
    const result = []
    for (let i = 0; i < data.length; i++) {
      if (i < dayCount) {
        result.push('-')
        continue
      }
      let sum = 0
      for (let j = 0; j < dayCount; j++) {
        sum += data[i - j].close
      }
      result.push(+(sum / dayCount).toFixed(3))
    }
    return result
  }

  // 净值曲线图配置
  const generateNetValueOption = (data: any[], benchmark?: any[]): echarts.EChartsOption => {
    return {
      backgroundColor: '#1a1a1a',
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        }
      },
      legend: {
        data: ['策略净值', '基准净值'],
        textStyle: {
          color: '#ccc'
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
        data: data.map(item => item.date),
        axisLabel: {
          color: '#ccc'
        }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: {
          formatter: '{value}',
          color: '#ccc'
        }
      },
      series: [
        {
          name: '策略净值',
          type: 'line',
          data: data.map(item => item.equity),
          smooth: true,
          lineStyle: {
            width: 2
          },
          areaStyle: {
            opacity: 0.1
          }
        },
        ...(benchmark ? [{
          name: '基准净值',
          type: 'line',
          data: benchmark.map(item => item.equity),
          smooth: true,
          lineStyle: {
            width: 1,
            type: 'dashed'
          }
        }] : [])
      ]
    }
  }

  onUnmounted(() => {
    disposeChart()
  })

  return {
    chartInstance,
    initChart,
    setChartOption,
    resizeChart,
    showLoading,
    hideLoading,
    getInstance,
    disposeChart,
    generateKLineOption,
    generateNetValueOption
  }
}