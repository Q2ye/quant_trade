<!--系统设置-->
<template>
  <div class="settings bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">系统设置</h1>
        </div>
      </div>
    </div>
    <div class="main-content">
    <n-card class="card-surface">
      <n-tabs v-model:value="activeTab">
        <!-- 交易设置 -->
        <n-tab-pane name="trade" tab="交易设置">
          <n-form label-width="180px">
            <n-form-item label="默认券商">
              <n-select
                v-model:value="tradeSettings.broker"
                style="width: 300px"
                :options="brokers"
              />
            </n-form-item>

            <n-form-item label="默认滑点">
              <n-input-number
                v-model:value="tradeSettings.slippage"
                :min="0"
                :max="0.1"
                :step="0.0005"
                style="width: 200px"
              />
              <span class="tip">（例如：0.001 表示 0.1%）</span>
            </n-form-item>

            <n-form-item label="默认手续费">
              <n-input-number
                v-model:value="tradeSettings.commission"
                :min="0"
                :max="0.01"
                :step="0.00005"
                style="width: 200px"
              />
              <span class="tip">（例如：0.0003 表示 万分之三）</span>
            </n-form-item>

            <n-form-item label="交易确认方式">
              <n-radio-group v-model:value="tradeSettings.confirmation">
                <n-radio value="auto">自动执行</n-radio>
                <n-radio value="manual">手动确认</n-radio>
              </n-radio-group>
            </n-form-item>
          </n-form>
        </n-tab-pane>

        <!-- 风险控制 -->
        <n-tab-pane name="risk" tab="风险控制">
          <n-form label-width="180px">
            <n-form-item label="单股最大仓位">
              <n-input-number
                v-model:value="riskSettings.maxPosition"
                :min="1"
                :max="100"
                :step="1"
                style="width: 200px"
              />
              <span class="tip">（例如：20 表示 20%）</span>
            </n-form-item>

            <n-form-item label="单日最大亏损">
              <n-input-number
                v-model:value="riskSettings.maxDailyLoss"
                :min="0.1"
                :max="10"
                :step="0.1"
                style="width: 200px"
              />
              <span class="tip">（例如：5 表示 5%）</span>
            </n-form-item>

            <n-form-item label="最大回撤阈值">
              <n-input-number
                v-model:value="riskSettings.maxDrawdown"
                :min="1"
                :max="30"
                :step="1"
                style="width: 200px"
              />
              <span class="tip">（例如：10 表示 10%）</span>
            </n-form-item>

            <n-form-item label="自动过滤ST股">
              <n-switch v-model:value="riskSettings.filterST" />
            </n-form-item>

            <n-form-item label="黑名单股票">
              <n-select
                v-model:value="riskSettings.blacklist"
                multiple
                filterable
                placeholder="输入股票代码或名称"
                :options="stockOptions"
                style="width: 400px"
              />
            </n-form-item>
          </n-form>
        </n-tab-pane>

        <!-- 数据设置 -->
        <n-tab-pane name="data" tab="数据设置">
          <n-form label-width="180px">
            <n-form-item label="数据源">
              <n-radio-group v-model:value="dataSettings.source">
                <n-radio value="tushare">Tushare</n-radio>
                <n-radio value="baostock">Baostock</n-radio>
              </n-radio-group>
            </n-form-item>

            <n-form-item label="Tushare Token">
              <n-input
                v-model:value="dataSettings.tushareToken"
                type="password"
                show-password-on="click"
                style="width: 400px"
              />
            </n-form-item>

            <n-form-item label="自动同步时间">
              <n-time-picker
                v-model:value="syncTimeValue"
                format="HH:mm"
                style="width: 200px"
              />
            </n-form-item>

            <n-form-item label="保留历史数据">
              <n-select
                v-model:value="dataSettings.keepHistory"
                style="width: 150px"
                :options="keepHistoryOptions"
              />
            </n-form-item>
          </n-form>
        </n-tab-pane>
      </n-tabs>

      <div class="action-bar">
        <n-space justify="center" :size="12">
          <n-button type="primary" class="hover-lift" :loading="saving" @click="saveSettings"
            >保存设置</n-button
          >
          <n-button class="hover-lift" @click="resetSettings">恢复默认</n-button>
        </n-space>
      </div>
    </n-card>
    </div><!-- .main-content -->
  </div>
</template>

<script>
export default {
  name: "Settings",
  data() {
    return {
      activeTab: "trade",
      saving: false,
      tradeSettings: {
        broker: "ht",
        slippage: 0.001,
        commission: 0.0003,
        confirmation: "manual",
      },
      riskSettings: {
        maxPosition: 20,
        maxDailyLoss: 5,
        maxDrawdown: 10,
        filterST: true,
        blacklist: ["600401.SH", "000982.SZ"],
      },
      dataSettings: {
        source: "tushare",
        tushareToken: "your_tushare_token",
        syncTime: "15:30",
        keepHistory: "3y",
      },
      brokers: [
        { label: "华泰证券", value: "ht" },
        { label: "广发证券", value: "gf" },
        { label: "招商证券", value: "zs" },
        { label: "中信证券", value: "zx" },
      ],
      stockOptions: [
        { label: "600401.SH 退市海润", value: "600401.SH" },
        { label: "000982.SZ *ST中绒", value: "000982.SZ" },
        { label: "002604.SZ ST龙力", value: "002604.SZ" },
      ],
      keepHistoryOptions: [
        { label: "1年", value: "1y" },
        { label: "2年", value: "2y" },
        { label: "3年", value: "3y" },
        { label: "全部", value: "all" },
      ],
    };
  },
  computed: {
    syncTimeValue: {
      get() {
        if (!this.dataSettings.syncTime) return null;
        const [h, m] = this.dataSettings.syncTime.split(":");
        return new Date(2024, 0, 1, parseInt(h), parseInt(m)).getTime();
      },
      set(val) {
        if (val) {
          const d = new Date(val);
          this.dataSettings.syncTime = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        }
      },
    },
  },
  methods: {
    async saveSettings() {
      this.saving = true;
      try {
        await new Promise((r) => setTimeout(r, 500));
        this.$message.success("设置已保存");
      } catch {
        this.$message.error("保存失败");
      } finally {
        this.saving = false;
      }
    },
    resetSettings() {
      this.tradeSettings = {
        broker: "ht",
        slippage: 0.001,
        commission: 0.0003,
        confirmation: "manual",
      };
      this.riskSettings = {
        maxPosition: 20,
        maxDailyLoss: 5,
        maxDrawdown: 10,
        filterST: true,
        blacklist: ["600401.SH", "000982.SZ"],
      };
      this.dataSettings = {
        source: "tushare",
        tushareToken: "your_tushare_token",
        syncTime: "15:30",
        keepHistory: "3y",
      };
      this.$message.info("已恢复默认设置");
    },
  },
};
</script>

<style scoped>
.settings {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.tip {
  color: var(--n-text-color-3);
  font-size: 12px;
  margin-left: 10px;
}

.action-bar {
  margin-top: 20px;
}
</style>
