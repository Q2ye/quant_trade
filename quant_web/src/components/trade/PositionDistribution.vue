<template>
  <div class="position-distribution">
    <div v-if="positions.length === 0" class="empty">暂无持仓数据</div>
    <el-row v-else>
      <el-col :span="12">
        <div ref="chart" style="height:250px;"></div>
      </el-col>
      <el-col :span="12">
        <el-table :data="positions" height="250">
          <el-table-column prop="symbol" label="代码" width="80"></el-table-column>
          <el-table-column prop="name" label="名称" width="100"></el-table-column>
          <el-table-column label="占比">
            <template #default="{ row }">
              <el-progress
                :percentage="row.ratio"
                :color="getProgressColor(row.ratio)"
                :show-text="false"></el-progress>
              <span>{{ row.ratio }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="industry" label="行业"></el-table-column>
        </el-table>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { ref, watch, onMounted } from 'vue';
import * as echarts from 'echarts';

export default {
  name: "PositionDistribution",
  props: {
    positions: Array
  },
  setup(props) {
    const chartDom = ref(null);

    const initChart = () => {
      if (!chartDom.value) return;
      const chart = echarts.init(chartDom.value);

      // 按行业聚合持仓比例
      const industryMap = {};
      props.positions.forEach(pos => {
        if (!industryMap[pos.industry]) {
          industryMap[pos.industry] = 0;
        }
        industryMap[pos.industry] += pos.ratio;
      });

      const data = Object.keys(industryMap).map(industry => ({
        name: industry,
        value: industryMap[industry]
      }));

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c}%'
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center',
          formatter: name => {
            const value = data.find(d => d.name === name)?.value || 0;
            return `${name}: ${value.toFixed(1)}%`;
          }
        },
        series: [
          {
            name: '持仓分布',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 10,
              borderColor: '#fff',
              borderWidth: 2
            },
            label: {
              show: false,
              position: 'center'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: '14',
                fontWeight: 'bold'
              }
            },
            labelLine: {
              show: false
            },
            data: data
          }
        ]
      };

      chart.setOption(option);
      window.addEventListener('resize', chart.resize);
    };

    const getProgressColor = (percentage) => {
      if (percentage > 15) return '#f56c6c';
      if (percentage > 10) return '#e6a23c';
      if (percentage > 5) return '#5cb87a';
      return '#909399';
    };

    onMounted(() => {
      if (props.positions.length > 0) {
        chartDom.value = document.querySelector('.position-distribution .el-col:first-child div');
        initChart();
      }
    });

    watch(() => props.positions, () => {
      if (props.positions.length > 0) {
        setTimeout(() => {
          chartDom.value = document.querySelector('.position-distribution .el-col:first-child div');
          initChart();
        }, 100);
      }
    });

    return {
      getProgressColor,
      chartDom
    };
  }
}
</script>

<style scoped>
.position-distribution {
  height: 100%;
}
.empty {
  height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}
</style>