<!--交易驾驶舱-->
<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- 资金曲线 -->
      <el-col :span="16">
        <el-card class="card">
          <div slot="header" class="clearfix">
            <span>资金曲线</span>
            <el-select v-model="timeRange" size="small" style="width:120px;float:right">
              <el-option label="7天" value="7d"></el-option>
              <el-option label="30天" value="30d"></el-option>
              <el-option label="90天" value="90d"></el-option>
            </el-select>
          </div>
          <NetValueChart :data="equityCurve" />
        </el-card>
      </el-col>

      <!-- 风险矩阵 -->
      <el-col :span="8">
        <el-card class="card">
          <div slot="header">
            <span>风险矩阵</span>
          </div>
          <RiskMatrix
            :maxDrawdown="riskData.maxDrawdown"
            :positionRatio="riskData.positionRatio"
            :dailyLoss="riskData.dailyLoss"
            :stocks="riskData.stocks" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- 持仓分布 -->
      <el-col :span="12">
        <el-card class="card">
          <div slot="header">
            <span>持仓分布</span>
          </div>
          <PositionDistribution :positions="positions" />
        </el-card>
      </el-col>

      <!-- 板块强度 -->
      <el-col :span="12">
        <el-card class="card">
          <div slot="header">
            <span>板块强度</span>
          </div>
          <IndustryStrength :industries="industryStrength" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- 今日成交记录 -->
      <el-col :span="12">
        <el-card class="card">
          <div slot="header">
            <span>今日成交</span>
          </div>
          <RecentTrades :trades="recentTrades" />
        </el-card>
      </el-col>

      <!-- 关联公告 -->
      <el-col :span="12">
        <el-card class="card">
          <div slot="header">
            <span>关联公告</span>
          </div>
          <StockAnnouncements :announcements="announcements" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import NetValueChart from '../../components/charts/NetValueChart.vue'
import RiskMatrix from '../../components/trade/RiskMatrix.vue'
import PositionDistribution from '../../components/trade/PositionDistribution.vue'
import IndustryStrength from '../Market/IndustryStrength.vue'
import RecentTrades from '../../components/trade/RecentTrades.vue'
import StockAnnouncements from '../../components/data/StockAnnouncements.vue'

export default {
  name: "Dashboard",
  components: {
    NetValueChart,
    RiskMatrix,
    PositionDistribution,
    IndustryStrength,
    RecentTrades,
    StockAnnouncements
  },
  data() {
    return {
      timeRange: '30d',
      equityCurve: [
        { date: '2023-07-10', value: 1000000 },
        { date: '2023-07-17', value: 1023500 },
        { date: '2023-07-24', value: 1056200 },
        { date: '2023-07-31', value: 1037800 },
        { date: '2023-08-07', value: 1074500 }
      ],
      riskData: {
        maxDrawdown: 4.2,
        positionRatio: 78.5,
        dailyLoss: 1.8,
        stocks: ['600519.SH', '000858.SZ', '601318.SH']
      },
      positions: [
        { symbol: '600519.SH', name: '贵州茅台', ratio: 18.2, industry: '食品饮料' },
        { symbol: '000858.SZ', name: '五粮液', ratio: 15.5, industry: '食品饮料' },
        { symbol: '601318.SH', name: '中国平安', ratio: 12.8, industry: '保险' },
        { symbol: '600036.SH', name: '招商银行', ratio: 11.2, industry: '银行' },
        { symbol: '600900.SH', name: '长江电力', ratio: 9.7, industry: '电力' }
      ],
      industryStrength: [
        { name: '计算机', change: 2.8, strength: 85 },
        { name: '通信', change: 1.5, strength: 78 },
        { name: '传媒', change: 3.2, strength: 92 },
        { name: '电子', change: -0.5, strength: 65 },
        { name: '医药生物', change: 0.8, strength: 72 }
      ],
      recentTrades: [
        { id: 1001, symbol: '600519.SH', name: '贵州茅台', direction: '买入', price: 1850.50, quantity: 100, time: '10:15:23' },
        { id: 1002, symbol: '000001.SH', name: '上证指数', direction: '卖出', price: 3245.67, quantity: 200, time: '09:42:11' },
        { id: 1003, symbol: '300750.SZ', name: '宁德时代', direction: '买入', price: 232.80, quantity: 300, time: '13:28:45' }
      ],
      announcements: [
        { symbol: '600519.SH', title: '贵州茅台2023年半年度业绩预告', type: '利好', time: '2023-08-08' },
        { symbol: '601318.SH', title: '中国平安7月保费收入公告', type: '中性', time: '2023-08-07' },
        { symbol: '000858.SZ', title: '五粮液股东减持计划公告', type: '利空', time: '2023-08-05' }
      ]
    }
  }
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.card {
  margin-bottom: 20px;
  height: 300px;
}

.clearfix:after {
  content: "";
  display: table;
  clear: both;
}
</style>