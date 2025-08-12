<!--系统设置-->
<!--系统设置-->
<template>
  <div class="settings">
    <el-card>
      <el-tabs v-model="activeTab">
        <!-- 交易设置 -->
        <el-tab-pane label="交易设置" name="trade">
          <el-form label-width="180px">
            <el-form-item label="默认券商">
              <el-select v-model="tradeSettings.broker" style="width: 300px;">
                <el-option
                  v-for="broker in brokers"
                  :key="broker.value"
                  :label="broker.label"
                  :value="broker.value" />
              </el-select>
            </el-form-item>

            <el-form-item label="默认滑点">
              <el-input-number
                v-model="tradeSettings.slippage"
                :min="0" :max="0.1" :step="0.0005"
                controls-position="right" />
              <span class="tip">（例如：0.001 表示 0.1%）</span>
            </el-form-item>

            <el-form-item label="默认手续费">
              <el-input-number
                v-model="tradeSettings.commission"
                :min="0" :max="0.01" :step="0.00005"
                controls-position="right" />
              <span class="tip">（例如：0.0003 表示 万分之三）</span>
            </el-form-item>

            <el-form-item label="交易确认方式">
              <el-radio-group v-model="tradeSettings.confirmation">
                <el-radio label="auto">自动执行</el-radio>
                <el-radio label="manual">手动确认</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 风险控制 -->
        <el-tab-pane label="风险控制" name="risk">
          <el-form label-width="180px">
            <el-form-item label="单股最大仓位">
              <el-input-number
                v-model="riskSettings.maxPosition"
                :min="1" :max="100" :step="1"
                controls-position="right" />
              <span class="tip">（例如：20 表示 20%）</span>
            </el-form-item>

            <el-form-item label="单日最大亏损">
              <el-input-number
                v-model="riskSettings.maxDailyLoss"
                :min="0.1" :max="10" :step="0.1"
                controls-position="right" />
              <span class="tip">（例如：5 表示 5%）</span>
            </el-form-item>

            <el-form-item label="最大回撤阈值">
              <el-input-number
                v-model="riskSettings.maxDrawdown"
                :min="1" :max="30" :step="1"
                controls-position="right" />
              <span class="tip">（例如：10 表示 10%）</span>
            </el-form-item>

            <el-form-item label="自动过滤ST股">
              <el-switch v-model="riskSettings.filterST" />
            </el-form-item>

            <el-form-item label="黑名单股票">
              <el-select
                v-model="riskSettings.blacklist"
                multiple
                filterable
                remote
                reserve-keyword
                placeholder="输入股票代码或名称"
                :remote-method="searchStocks"
                style="width: 400px;">
                <el-option
                  v-for="stock in stockOptions"
                  :key="stock.value"
                  :label="`${stock.value} ${stock.label}`"
                  :value="stock.value" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 数据设置 -->
        <el-tab-pane label="数据设置" name="data">
          <el-form label-width="180px">
            <el-form-item label="数据源">
              <el-radio-group v-model="dataSettings.source">
                <el-radio label="tushare">Tushare</el-radio>
                <el-radio label="baostock">Baostock</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="Tushare Token">
              <el-input
                v-model="dataSettings.tushareToken"
                type="password"
                show-password
                style="width: 400px;" />
            </el-form-item>

            <el-form-item label="自动同步时间">
              <el-time-select
                v-model="dataSettings.syncTime"
                placeholder="每日同步时间"
                :picker-options="{ start: '00:00', step: '00:30', end: '23:30' }"
              />
            </el-form-item>

            <el-form-item label="保留历史数据">
              <el-select v-model="dataSettings.keepHistory" style="width: 150px;">
                <el-option label="1年" value="1y"></el-option>
                <el-option label="2年" value="2y"></el-option>
                <el-option label="3年" value="3y"></el-option>
                <el-option label="全部" value="all"></el-option>
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="action-bar">
        <el-button type="primary" @click="saveSettings">保存设置</el-button>
        <el-button @click="resetSettings">恢复默认</el-button>
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: "Settings",
  data() {
    return {
      activeTab: 'trade',
      tradeSettings: {
        broker: 'ht',
        slippage: 0.001,
        commission: 0.0003,
        confirmation: 'manual'
      },
      riskSettings: {
        maxPosition: 20,
        maxDailyLoss: 5,
        maxDrawdown: 10,
        filterST: true,
        blacklist: ['600401.SH', '000982.SZ']
      },
      dataSettings: {
        source: 'tushare',
        tushareToken: 'your_tushare_token',
        syncTime: '15:30',
        keepHistory: '3y'
      },
      brokers: [
        { value: 'ht', label: '华泰证券' },
        { value: 'gf', label: '广发证券' },
        { value: 'zs', label: '招商证券' },
        { value: 'zx', label: '中信证券' }
      ],
      stockOptions: [
        { value: '600401.SH', label: '退市海润' },
        { value: '000982.SZ', label: '*ST中绒' },
        { value: '002604.SZ', label: 'ST龙力' }
      ]
    }
  },
  methods: {
    searchStocks(query) {
      // 实际项目中调用API搜索股票
      if (query !== '') {
        this.stockOptions = [
          { value: '600401.SH', label: '退市海润' },
          { value: '000982.SZ', label: '*ST中绒' },
          { value: '002604.SZ', label: 'ST龙力' },
          { value: '600856.SH', label: 'ST中天' }
        ].filter(item => {
          return item.label.toLowerCase().includes(query.toLowerCase()) ||
                 item.value.toLowerCase().includes(query.toLowerCase());
        });
      } else {
        this.stockOptions = [];
      }
    },
    saveSettings() {
      // 实际项目中保存设置到服务器
      this.$message.success('设置已保存');
    },
    resetSettings() {
      // 重置为默认设置
      this.tradeSettings = {
        broker: 'ht',
        slippage: 0.001,
        commission: 0.0003,
        confirmation: 'manual'
      };
      this.riskSettings = {
        maxPosition: 20,
        maxDailyLoss: 5,
        maxDrawdown: 10,
        filterST: true,
        blacklist: ['600401.SH', '000982.SZ']
      };
      this.dataSettings = {
        source: 'tushare',
        tushareToken: 'your_tushare_token',
        syncTime: '15:30',
        keepHistory: '3y'
      };
      this.$message.info('已恢复默认设置');
    }
  }
}
</script>

<style scoped>
.settings {
  padding: 20px;
}

.tip {
  color: #909399;
  font-size: 12px;
  margin-left: 10px;
}

.action-bar {
  margin-top: 20px;
  text-align: center;
}
</style>