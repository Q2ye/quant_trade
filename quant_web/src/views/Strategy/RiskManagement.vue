<!-- 风险管理-->
<!-- 风险管理-->
<script>
export default {
  name: "RiskManagement",
  data() {
    return {
      activeTab: 'account',
      accountRiskRules: [
        { id: 1, name: '单日最大亏损', value: 5, unit: '%', enabled: true, description: '账户单日亏损达到该值时触发警报' },
        { id: 2, name: '最大回撤', value: 15, unit: '%', enabled: true, description: '账户净值从最高点回撤达到该值时触发警报' },
        { id: 3, name: '仓位上限', value: 80, unit: '%', enabled: true, description: '账户总持仓市值占总资产的比例上限' }
      ],
      strategyRiskRules: [
        { id: 1, name: '单股最大仓位', value: 20, unit: '%', enabled: true, description: '单个股票持仓市值占总资产的比例上限' },
        { id: 2, name: '单策略最大亏损', value: 10, unit: '%', enabled: true, description: '单个策略亏损达到该值时自动停止' },
        { id: 3, name: '单日最大交易次数', value: 5, unit: '次', enabled: true, description: '单个策略单日最大交易次数限制' },
        { id: 4, name: '最大持仓天数', value: 10, unit: '天', enabled: false, description: '单个股票最大持仓天数限制' }
      ],
      alertRecords: [
        { id: 1, rule: '单日最大亏损', time: '2023-08-10 14:30:25', level: 'high', account: '主账户', value: -5.2, status: '已处理' },
        { id: 2, rule: '单股最大仓位', time: '2023-08-09 10:15:42', level: 'medium', account: '策略A', value: 22.5, status: '处理中' },
        { id: 3, rule: '最大回撤', time: '2023-08-08 15:45:18', level: 'high', account: '主账户', value: -16.8, status: '已忽略' },
        { id: 4, rule: '单策略最大亏损', time: '2023-08-07 11:20:33', level: 'critical', account: '策略B', value: -12.3, status: '已处理' }
      ],
      newRule: {
        type: 'account',
        name: '',
        value: '',
        unit: '%',
        enabled: true,
        description: ''
      },
      ruleTypes: [
        { value: 'account', label: '账户级规则' },
        { value: 'strategy', label: '策略级规则' }
      ],
      unitOptions: ['%', '元', '次', '天', '手']
    };
  },
  methods: {
    addRule() {
      if (!this.newRule.name || !this.newRule.value) {
        this.$message.warning('请填写规则名称和值');
        return;
      }

      const rule = {
        id: Date.now(),
        ...this.newRule,
        value: parseFloat(this.newRule.value)
      };

      if (this.newRule.type === 'account') {
        this.accountRiskRules.push(rule);
      } else {
        this.strategyRiskRules.push(rule);
      }

      this.$message.success('规则添加成功');

      // 重置表单
      this.newRule = {
        type: 'account',
        name: '',
        value: '',
        unit: '%',
        enabled: true,
        description: ''
      };
    },
    removeRule(ruleId, type) {
      if (type === 'account') {
        this.accountRiskRules = this.accountRiskRules.filter(r => r.id !== ruleId);
      } else {
        this.strategyRiskRules = this.strategyRiskRules.filter(r => r.id !== ruleId);
      }
      this.$message.info('规则已删除');
    },
    toggleRuleStatus(rule, type) {
      rule.enabled = !rule.enabled;
      const action = rule.enabled ? '启用' : '禁用';
      this.$message.success(`${rule.name}规则已${action}`);
    },
    resolveAlert(alertId) {
      const alert = this.alertRecords.find(a => a.id === alertId);
      if (alert) {
        alert.status = '已处理';
        this.$message.success('警报已标记为已处理');
      }
    },
    ignoreAlert(alertId) {
      const alert = this.alertRecords.find(a => a.id === alertId);
      if (alert) {
        alert.status = '已忽略';
        this.$message.info('警报已忽略');
      }
    }
  },
  computed: {
    criticalAlerts() {
      return this.alertRecords.filter(a => a.level === 'critical');
    },
    activeAlerts() {
      return this.alertRecords.filter(a => a.status === '处理中');
    }
  }
};
</script>

<template>
  <div class="risk-management">
    <div class="risk-header">
      <h2>风险管理</h2>
      <div class="risk-summary">
        <div class="summary-card critical">
          <div class="summary-title">严重警报</div>
          <div class="summary-value">{{ criticalAlerts.length }}</div>
        </div>
        <div class="summary-card active">
          <div class="summary-title">活跃警报</div>
          <div class="summary-value">{{ activeAlerts.length }}</div>
        </div>
        <div class="summary-card rules">
          <div class="summary-title">生效规则</div>
          <div class="summary-value">{{ accountRiskRules.filter(r => r.enabled).length + strategyRiskRules.filter(r => r.enabled).length }}</div>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="risk-tabs">
      <!-- 规则配置标签页 -->
      <el-tab-pane label="规则配置" name="rules">
        <div class="rules-container">
          <div class="rule-types">
            <div
              :class="['rule-type', { 'active': activeTab === 'account' }]"
              @click="activeTab = 'account'"
            >
              账户级风险规则
            </div>
            <div
              :class="['rule-type', { 'active': activeTab === 'strategy' }]"
              @click="activeTab = 'strategy'"
            >
              策略级风险规则
            </div>
          </div>

          <!-- 账户级风险规则 -->
          <div v-show="activeTab === 'account'" class="rule-section">
            <div class="section-header">
              <h3>账户级风险规则</h3>
              <el-button type="primary" size="small" @click="activeTab = 'new'">添加规则</el-button>
            </div>

            <el-table :data="accountRiskRules" style="width: 100%">
              <el-table-column prop="name" label="规则名称" width="180"></el-table-column>
              <el-table-column label="阈值">
                <template #default="{ row }">
                  <span class="rule-value">{{ row.value }}{{ row.unit }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述"></el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-switch
                    v-model="row.enabled"
                    active-color="#13ce66"
                    inactive-color="#ff4949"
                    @change="toggleRuleStatus(row, 'account')"
                  ></el-switch>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button type="danger" size="mini" @click="removeRule(row.id, 'account')">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 策略级风险规则 -->
          <div v-show="activeTab === 'strategy'" class="rule-section">
            <div class="section-header">
              <h3>策略级风险规则</h3>
              <el-button type="primary" size="small" @click="activeTab = 'new'">添加规则</el-button>
            </div>

            <el-table :data="strategyRiskRules" style="width: 100%">
              <el-table-column prop="name" label="规则名称" width="180"></el-table-column>
              <el-table-column label="阈值">
                <template #default="{ row }">
                  <span class="rule-value">{{ row.value }}{{ row.unit }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述"></el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-switch
                    v-model="row.enabled"
                    active-color="#13ce66"
                    inactive-color="#ff4949"
                    @click="toggleRuleStatus(row, 'strategy')"
                  ></el-switch>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button type="danger" size="mini" @click="removeRule(row.id, 'strategy')">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 添加新规则 -->
          <div v-show="activeTab === 'new'" class="new-rule-section">
            <div class="section-header">
              <h3>添加新规则</h3>
              <el-button icon="el-icon-back" @click="activeTab = 'account'">返回</el-button>
            </div>

            <div class="rule-form">
              <el-form :model="newRule" label-width="120px">
                <el-form-item label="规则类型">
                  <el-radio-group v-model="newRule.type">
                    <el-radio label="account">账户级规则</el-radio>
                    <el-radio label="strategy">策略级规则</el-radio>
                  </el-radio-group>
                </el-form-item>

                <el-form-item label="规则名称" required>
                  <el-input v-model="newRule.name" placeholder="输入规则名称"></el-input>
                </el-form-item>

                <el-form-item label="规则值" required>
                  <div class="value-input">
                    <el-input v-model="newRule.value" placeholder="输入阈值"></el-input>
                    <el-select v-model="newRule.unit" style="width: 100px; margin-left: 10px;">
                      <el-option v-for="unit in unitOptions" :key="unit" :label="unit" :value="unit"></el-option>
                    </el-select>
                  </div>
                </el-form-item>

                <el-form-item label="规则描述">
                  <el-input
                    v-model="newRule.description"
                    type="textarea"
                    :rows="3"
                    placeholder="输入规则描述"
                  ></el-input>
                </el-form-item>

                <el-form-item label="状态">
                  <el-switch
                    v-model="newRule.enabled"
                    active-text="启用"
                    inactive-text="禁用"
                  ></el-switch>
                </el-form-item>

                <el-form-item>
                  <el-button type="primary" @click="addRule">保存规则</el-button>
                  <el-button @click="activeTab = 'account'">取消</el-button>
                </el-form-item>
              </el-form>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 警报记录标签页 -->
      <el-tab-pane label="警报记录" name="alerts">
        <div class="alerts-container">
          <div class="alerts-filter">
            <el-select v-model="filterLevel" placeholder="全部级别" clearable>
              <el-option label="严重" value="critical"></el-option>
              <el-option label="高" value="high"></el-option>
              <el-option label="中" value="medium"></el-option>
              <el-option label="低" value="low"></el-option>
            </el-select>

            <el-select v-model="filterStatus" placeholder="全部状态" clearable>
              <el-option label="处理中" value="处理中"></el-option>
              <el-option label="已处理" value="已处理"></el-option>
              <el-option label="已忽略" value="已忽略"></el-option>
            </el-select>

            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            ></el-date-picker>
          </div>

          <el-table :data="alertRecords" style="width: 100%">
            <el-table-column label="级别" width="100">
              <template #default="{ row }">
                <el-tag :type="row.level === 'critical' ? 'danger' : row.level === 'high' ? 'warning' : 'info'">
                  {{ row.level === 'critical' ? '严重' : row.level === 'high' ? '高' : row.level === 'medium' ? '中' : '低' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="rule" label="规则" width="150"></el-table-column>
            <el-table-column prop="time" label="时间" width="180"></el-table-column>
            <el-table-column prop="account" label="账户/策略" width="120"></el-table-column>
            <el-table-column label="实际值">
              <template #default="{ row }">
                <span :class="row.value < 0 ? 'negative-value' : 'positive-value'">
                  {{ row.value > 0 ? '+' : '' }}{{ row.value }}{{ row.rule.includes('亏损') || row.rule.includes('回撤') ? '%' : '' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === '已处理' ? 'success' : row.status === '处理中' ? 'warning' : 'info'">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === '处理中'"
                  type="success"
                  size="mini"
                  @click="resolveAlert(row.id)"
                >
                  标记为已处理
                </el-button>
                <el-button
                  v-if="row.status === '处理中'"
                  type="info"
                  size="mini"
                  @click="ignoreAlert(row.id)"
                >
                  忽略
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.risk-management {
  padding: 20px;
  background-color: #121a29;
  color: #e0e0e0;
  height: 100%;
  overflow-y: auto;
}

.risk-header {
  margin-bottom: 25px;
}

.risk-header h2 {
  margin-top: 0;
  color: #64b5f6;
  padding-bottom: 15px;
  border-bottom: 1px solid #2a3a5a;
}

.risk-summary {
  display: flex;
  gap: 20px;
  margin-top: 20px;
}

.summary-card {
  flex: 1;
  background: #1a2439;
  border-radius: 8px;
  padding: 15px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.summary-card.critical {
  border-top: 4px solid #f44336;
}

.summary-card.active {
  border-top: 4px solid #ff9800;
}

.summary-card.rules {
  border-top: 4px solid #4caf50;
}

.summary-title {
  font-size: 14px;
  color: #9da8b8;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
}

.risk-tabs {
  background: #1a2439;
  border-radius: 8px;
  overflow: hidden;
}

.rules-container {
  padding: 20px;
}

.rule-types {
  display: flex;
  margin-bottom: 20px;
  background: #152136;
  border-radius: 6px;
  overflow: hidden;
}

.rule-type {
  flex: 1;
  text-align: center;
  padding: 12px;
  cursor: pointer;
  transition: background 0.3s;
}

.rule-type.active {
  background: #2a3a5a;
  color: #64b5f6;
  font-weight: bold;
}

.rule-type:hover:not(.active) {
  background: #1d2c46;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
  color: #64b5f6;
}

.rule-section, .new-rule-section {
  background: #152136;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.rule-value {
  font-weight: bold;
  color: #ff9800;
}

.new-rule-section {
  animation: fadeIn 0.3s ease;
}

.rule-form {
  max-width: 700px;
  margin: 0 auto;
}

.value-input {
  display: flex;
}

.alerts-container {
  padding: 20px;
}

.alerts-filter {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.positive-value {
  color: #f44336;
  font-weight: bold;
}

.negative-value {
  color: #4caf50;
  font-weight: bold;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

:deep(.el-table) {
  background: transparent;
  color: #e0e0e0;
}

:deep(.el-table th) {
  background: #152136;
  color: #64b5f6;
}

:deep(.el-table tr) {
  background: #1a2439;
}

:deep(.el-table--enable-row-hover .el-table__body tr:hover>td) {
  background: #152136;
}

:deep(.el-tabs__item) {
  color: #9da8b8;
}

:deep(.el-tabs__item.is-active) {
  color: #64b5f6;
}

:deep(.el-tabs__active-bar) {
  background: #64b5f6;
}

:deep(.el-tabs__nav-wrap::after) {
  background: #2a3a5a;
}
</style>