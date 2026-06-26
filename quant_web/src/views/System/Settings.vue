<!--系统设置-->
<template>
  <div class="settings bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section"><h1 class="page-title">系统设置</h1><p class="page-description">安全策略、通知渠道与系统维护参数配置</p></div>
      </div>
    </div>
    <div class="main-content">
      <n-skeleton v-if="loading" :text="true" :repeat="12" />
      <n-result v-else-if="error" status="500" title="加载失败" description="获取设置数据失败">
        <template #footer><n-button type="primary" @click="loadSettings">重试</n-button></template>
      </n-result>
      <template v-else>
        <!-- 三列等高 -->
        <n-grid :x-gap="16" :cols="3" class="settings-grid">
          <!-- 安全设置 -->
          <n-grid-item class="settings-item">
            <n-card :class="tokens.surface.card" size="small" class="settings-card">
              <template #header>
                <div class="card-head"><Icon icon="mdi:shield-lock" /><span>安全设置</span></div>
              </template>
              <div class="setting-list">
                <div class="setting-row">
                  <span class="s-label">会话超时</span>
                  <n-input-number v-model:value="form.session_timeout" :min="5" :max="1440" size="small" style="width:80px" />
                  <span class="s-unit">分钟</span>
                </div>
                <div class="setting-row">
                  <span class="s-label">最大登录失败</span>
                  <n-input-number v-model:value="form.max_login_attempts" :min="3" :max="20" size="small" style="width:80px" />
                  <span class="s-unit">次</span>
                </div>
                <div class="setting-row">
                  <span class="s-label">锁定时长</span>
                  <n-input-number v-model:value="form.lockout_minutes" :min="5" :max="1440" size="small" style="width:80px" />
                  <span class="s-unit">分钟</span>
                </div>
                <div class="setting-row">
                  <span class="s-label">密码最小长度</span>
                  <n-input-number v-model:value="form.password_min_length" :min="6" :max="32" size="small" style="width:80px" />
                  <span class="s-unit">字符</span>
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- 通知设置 -->
          <n-grid-item class="settings-item">
            <n-card :class="tokens.surface.card" size="small" class="settings-card">
              <template #header>
                <div class="card-head"><Icon icon="mdi:bell-ring" /><span>通知设置</span></div>
              </template>
              <div class="setting-list">
                <div class="setting-row">
                  <Icon icon="mdi:message-badge" :style="{color: form.dingtalk_enabled ? '#1890FF' : 'var(--n-text-color-3)'}" />
                  <span class="s-label">钉钉通知</span>
                  <n-switch v-model:value="form.dingtalk_enabled" size="small" />
                </div>
                <div class="setting-row">
                  <Icon icon="mdi:wechat" :style="{color: form.wechat_enabled ? '#07C160' : 'var(--n-text-color-3)'}" />
                  <span class="s-label">微信通知</span>
                  <n-switch v-model:value="form.wechat_enabled" size="small" />
                </div>
                <div class="setting-row">
                  <Icon icon="mdi:email" :style="{color: form.email_enabled ? '#EA4335' : 'var(--n-text-color-3)'}" />
                  <span class="s-label">邮件通知</span>
                  <n-switch v-model:value="form.email_enabled" size="small" />
                </div>
                <div class="setting-row">
                  <Icon icon="mdi:alert-circle" :style="{color: form.risk_alert_enabled ? '#F59E0B' : 'var(--n-text-color-3)'}" />
                  <span class="s-label">风控告警</span>
                  <n-switch v-model:value="form.risk_alert_enabled" size="small" />
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- 维护设置 -->
          <n-grid-item class="settings-item">
            <n-card :class="tokens.surface.card" size="small" class="settings-card">
              <template #header>
                <div class="card-head"><Icon icon="mdi:cog-sync" /><span>维护设置</span></div>
              </template>
              <div class="setting-list">
                <div class="setting-row">
                  <span class="s-label">审计日志保留</span>
                  <n-input-number v-model:value="form.audit_retention_days" :min="7" :max="365" size="small" style="width:80px" />
                  <span class="s-unit">天</span>
                </div>
                <div class="setting-row">
                  <span class="s-label">计划清理时间</span>
                  <n-time-picker v-model:value="form.cleanup_time" format="HH:mm" size="small" style="width:100px" />
                </div>
                <div class="setting-row">
                  <span class="s-label">自动清理过期数据</span>
                  <n-switch v-model:value="form.auto_cleanup" size="small" />
                </div>
                <div class="setting-row setting-row-spacer" />
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- 保存按钮独立一行，居中 -->
        <div class="action-bar">
          <n-space :size="12">
            <n-button type="primary" :loading="saving" @click="saveSettings">保存设置</n-button>
            <n-button @click="loadSettings">重新加载</n-button>
          </n-space>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useMessage } from "naive-ui"
import { tokens } from "@/styles/design-tokens"
import systemAPI from "@/api/system"

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const error = ref(false)

const form = ref({
  session_timeout: 30,
  max_login_attempts: 5,
  lockout_minutes: 30,
  password_min_length: 8,
  dingtalk_enabled: false,
  wechat_enabled: false,
  email_enabled: false,
  risk_alert_enabled: true,
  audit_retention_days: 90,
  auto_cleanup: false,
  cleanup_time: (() => { const d = new Date(); d.setHours(3, 0, 0, 0); return d.getTime() })(),
})

async function loadSettings() {
  loading.value = true; error.value = false
  try {
    const res = await systemAPI.getSystemSettings()
    if (res) {
      if (res.security) Object.assign(form.value, res.security)
      if (res.notification) {
        form.value.dingtalk_enabled = res.notification.dingtalk_enabled ?? form.value.dingtalk_enabled
        form.value.wechat_enabled = res.notification.wechat_enabled ?? form.value.wechat_enabled
        form.value.email_enabled = res.notification.email_enabled ?? form.value.email_enabled
        form.value.risk_alert_enabled = res.notification.risk_alert_enabled ?? form.value.risk_alert_enabled
      }
    }
  } catch { error.value = true }
  finally { loading.value = false }
}

async function saveSettings() {
  saving.value = true
  try {
    await systemAPI.updateSystemSettings({
      security: {
        session_timeout: form.value.session_timeout,
        max_login_attempts: form.value.max_login_attempts,
        lockout_minutes: form.value.lockout_minutes,
        password_min_length: form.value.password_min_length,
      },
      notification: {
        dingtalk_enabled: form.value.dingtalk_enabled,
        wechat_enabled: form.value.wechat_enabled,
        email_enabled: form.value.email_enabled,
        risk_alert_enabled: form.value.risk_alert_enabled,
      },
      maintenance: {
        audit_retention_days: form.value.audit_retention_days,
        auto_cleanup: form.value.auto_cleanup,
      },
    })
    message.success("设置已保存")
  } catch { message.error("保存失败") }
  finally { saving.value = false }
}

onMounted(() => loadSettings())
</script>

<style scoped>
.settings { padding: 0; padding-bottom: 24px; height: 100%; overflow-y: auto; }

/* 卡片 header 图标+文字 */
.card-head { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; }

/* 统一的设置项列表 */
.setting-list { display: flex; flex-direction: column; gap: 2px; }
.setting-row {
  display: flex; align-items: center; gap: 10px;
  height: 44px;
  padding: 0;
  border-bottom: 1px solid var(--n-border-color, rgba(255,255,255,.06));
}
.setting-row:last-child { border-bottom: none; }
.setting-row-spacer { border-bottom: none !important; }

.s-label { flex: 1; font-size: 13px; color: var(--n-text-color-2); }
.s-unit { font-size: 12px; color: var(--n-text-color-3); min-width: 28px; }

.action-bar { margin-top: 24px; display: flex; justify-content: center; }

.settings-grid { align-items: stretch; }
.settings-item { display: flex; }
.settings-card { flex: 1; display: flex; flex-direction: column; }
.settings-card > :deep(.n-card__content) { flex: 1; }
</style>
