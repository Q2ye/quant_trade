<!--系统仪表盘-->
<template>
  <div class="dashboard bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section"><h1 class="page-title">系统仪表盘</h1><p class="page-description">CPU、内存、磁盘、服务连接状态与资源趋势总览</p></div>
        <div class="header-actions">
          <span class="refresh-time">更新于 {{ lastRefresh }}</span>
          <n-button class="action-btn" @click="refreshAll" quaternary><template #icon><Icon icon="mdi:refresh" /></template></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result v-if="error" status="500" title="加载失败" description="获取监控数据失败">
        <template #footer><n-button type="primary" @click="refreshAll">重试</n-button></template>
      </n-result>

      <template v-else-if="loading && !hasData">
        <n-grid :x-gap="16" :y-gap="16" :cols="3"><n-grid-item v-for="i in 6" :key="i"><n-card :class="tokens.surface.card"><n-skeleton :text="true" :repeat="4" /></n-card></n-grid-item></n-grid>
      </template>

      <n-empty v-else-if="!hasData" description="暂无监控数据" style="margin-top: 60px" />

      <template v-else>
        <!-- ===== Row 1: 资源卡片 3列 ===== -->
        <n-grid :x-gap="16" :y-gap="16" :cols="3" class="row-equal">
          <!-- CPU -->
          <n-grid-item>
            <n-card :class="[tokens.surface.card, tokens.motion.stagger, 'card-fill']" size="small">
              <template #header><div class="card-hdr"><Icon icon="mdi:cpu-64-bit" :style="{color:cpuColor}" /><span>CPU</span></div></template>
              <div class="res-grid">
                <n-progress type="circle" :percentage="cpuPercent" :color="cpuColor" :rail-color="railColor" size="100" stroke-width="10">
                  <span class="pct-num">{{ cpuPercent }}<small>%</small></span>
                </n-progress>
                <div class="res-stats">
                  <div class="stat-line"><span class="stat-k">核心数</span><span class="stat-v">{{ cpuCores }}</span></div>
                  <div class="stat-line"><span class="stat-k">状态</span><span class="stat-v" :style="{color:cpuColor}">{{ cpuLevel }}</span></div>
                  <div class="stat-line"><span class="stat-k">运行</span><span class="stat-v">{{ sysUptime }}</span></div>
                  <div class="stat-line"><span class="stat-k">进程</span><span class="stat-v">--</span></div>
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- 内存 & 磁盘 -->
          <n-grid-item>
            <n-card :class="[tokens.surface.card, tokens.motion.stagger, 'card-fill']" size="small">
              <template #header><div class="card-hdr"><Icon icon="mdi:memory" :style="{color:memColor}" /><span>内存 &amp; 磁盘</span></div></template>
              <div class="dual-section">
                <!-- 内存 -->
                <div class="section-block">
                  <div class="section-top"><Icon icon="mdi:memory" :style="{color:memColor,fontSize:'16px'}" /><span>内存</span><span class="section-val">{{ memPercent }}%</span></div>
                  <n-progress :percentage="memPercent" :color="memColor" :rail-color="railColor" :height="8" :show-indicator="false" />
                  <div class="section-sub">{{ fmtBytes(memUsed) }} / {{ fmtBytes(memTotal) }}</div>
                </div>
                <!-- 磁盘 -->
                <div class="section-block">
                  <div class="section-top"><Icon icon="mdi:harddisk" style="font-size:16px;color:#F59E0B" /><span>磁盘</span><span class="section-val">{{ diskPercent }}%</span></div>
                  <n-progress :percentage="diskPercent" color="#F59E0B" :rail-color="railColor" :height="8" :show-indicator="false" />
                  <div class="section-sub">{{ fmtBytes(diskUsed) }} / {{ fmtBytes(diskTotal) }}</div>
                </div>
              </div>
            </n-card>
          </n-grid-item>

          <!-- 系统健康 -->
          <n-grid-item>
            <n-card :class="[tokens.surface.card, tokens.motion.stagger, 'card-fill']" size="small">
              <template #header><div class="card-hdr"><Icon icon="mdi:heart-pulse" :style="{color:healthColor}" /><span>系统健康</span></div></template>
              <div class="health-layout">
                <div class="hl-left">
                  <div class="hl-score" :style="{color:healthColor}">{{ healthScore }}</div>
                  <div class="hl-label">/ 100</div>
                  <div class="hl-status" :style="{color:healthColor}">{{ healthLabel }}</div>
                </div>
                <div class="hl-right">
                  <div v-for="c in connections" :key="c.name" class="hl-conn">
                    <Icon :icon="c.icon" :style="{color: c.ok ? '#22C55E' : '#EF4444', fontSize:'14px'}" />
                    <span class="hl-cname">{{ c.name }}</span>
                    <span class="hl-cval">{{ c.text }}</span>
                  </div>
                </div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- ===== Row 2: 趋势图 + 系统信息 ===== -->
        <n-grid :x-gap="16" :y-gap="16" :cols="3" class="row-equal" style="margin-top: 16px">
          <n-grid-item :span="2">
            <n-card :class="[tokens.surface.card, tokens.motion.stagger, 'card-fill']" size="small" title="资源趋势 (最近 30 次)">
              <template #header-extra>
                <n-tag size="tiny" :type="cpuhistory.length<2?'default':'info'">{{ cpuhistory.length }} 点</n-tag>
              </template>
              <n-empty v-if="cpuhistory.length<2" description="采集数据不足" size="small" style="height:160px" />
              <div v-else ref="trendChartRef" class="trend-chart"></div>
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-card :class="[tokens.surface.card, tokens.motion.stagger, 'card-fill']" size="small" title="系统信息">
              <div class="kv-list">
                <div class="kv-item"><span class="kv-key">版本</span><span class="kv-val">{{ sysInfo.version }}</span></div>
                <div class="kv-item"><span class="kv-key">运行时间</span><span class="kv-val">{{ sysInfo.uptime }}</span></div>
                <div class="kv-item"><span class="kv-key">在线用户</span><span class="kv-val">{{ sysInfo.activeUsers }} / {{ sysInfo.totalUsers }}</span></div>
                <div class="kv-item"><span class="kv-key">数据库表</span><span class="kv-val">{{ dbInfo.total_tables || '--' }}</span></div>
                <div class="kv-item"><span class="kv-key">股票记录</span><span class="kv-val">{{ fmtNum(dbInfo.stock_data_count) }}</span></div>
                <div class="kv-item"><span class="kv-key">活动连接</span><span class="kv-val">{{ dbInfo.active_connections || 0 }}</span></div>
                <div class="kv-item"><span class="kv-key">DB 大小</span><span class="kv-val">{{ dbInfo.size || '--' }}</span></div>
              </div>
            </n-card>
          </n-grid-item>
        </n-grid>

        <!-- ===== Row 3: 最近日志 ===== -->
        <n-card :class="[tokens.surface.card, tokens.motion.stagger]" title="最近日志" size="small" style="margin-top:16px">
          <template #header-extra><n-button text size="tiny" @click="$router.push('/system/logs')">查看全部</n-button></template>
          <n-empty v-if="recentLogs.length===0" description="暂无日志" size="small" />
          <n-data-table v-else :columns="logColumns" :data="recentLogs.slice(0,10)" :row-key="(_row: any, i: number) => i" size="small" :bordered="false" :single-line="true" />
        </n-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, h } from "vue"
import { tokens } from "@/styles/design-tokens"
import systemAPI from "@/api/system"
import type { DataTableColumn } from "naive-ui"
import { createChart, ColorType, LineSeries } from "lightweight-charts"

const loading = ref(false)
const error = ref(false)
const lastRefresh = ref("--:--:--")
let _timer: ReturnType<typeof setInterval> | null = null

const resourceUsage = ref<any>(null)
const connectionStatus = ref<any>(null)
const systemStatus = ref<any>(null)
const dbStatus = ref<any>(null)
const recentLogs = ref<any[]>([])

const cpuhistory = ref<{ time: string; cpu: number; mem: number }[]>([])
const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: ReturnType<typeof createChart> | null = null
let cpuSeries: any = null
let memSeries: any = null

// ---- computed ----
const hasData = computed(() => !!(resourceUsage.value || systemStatus.value))
const cpuPercent = computed(() => resourceUsage.value?.cpu_percent ?? 0)
const cpuCores = computed(() => resourceUsage.value?.cpu_cores ?? '--')
const memPercent = computed(() => resourceUsage.value?.memory_percent ?? 0)
const memUsed = computed(() => resourceUsage.value?.memory_used ?? 0)
const memTotal = computed(() => resourceUsage.value?.memory_total ?? 0)
const diskPercent = computed(() => resourceUsage.value?.disk_usage ?? 0)
const diskUsed = computed(() => resourceUsage.value?.disk_used ?? 0)
const diskTotal = computed(() => resourceUsage.value?.disk_total ?? 0)
const sysUptime = computed(() => systemStatus.value?.uptime || '--')
const cpuColor = computed(() => thresholdColor(cpuPercent.value))
const memColor = computed(() => thresholdColor(memPercent.value))
const railColor = 'var(--n-color-embedded)'

const cpuLevel = computed(() => cpuPercent.value >= 80 ? '繁忙' : cpuPercent.value >= 50 ? '正常' : '空闲')

const connections = computed(() => {
  const c = connectionStatus.value || {}
  return [
    { name: "数据库", icon: "mdi:database", ok: !!c.database, text: c.database_latency_ms ? `${c.database_latency_ms}ms` : (c.database ? 'OK' : '断开') },
    { name: "Redis", icon: "mdi:server", ok: !!c.redis, text: c.redis ? 'OK' : '断开' },
    { name: "Tushare", icon: "mdi:cloud", ok: !!c.tushare, text: c.tushare ? '已配置' : '未配置' },
    { name: "交易网关", icon: "mdi:swap-horizontal", ok: !!c.broker, text: c.broker_mode || (c.broker ? 'OK' : '未连接') },
  ]
})

const healthScore = computed(() => {
  let score = 100
  if (cpuPercent.value > 80) score -= 20; else if (cpuPercent.value > 50) score -= 8
  if (memPercent.value > 80) score -= 20; else if (memPercent.value > 50) score -= 8
  if (!connections.value[0]?.ok) score -= 25
  if (!connections.value[1]?.ok) score -= 10
  return Math.max(0, score)
})
const healthColor = computed(() => healthScore.value >= 80 ? '#22C55E' : healthScore.value >= 50 ? '#F59E0B' : '#EF4444')
const healthLabel = computed(() => healthScore.value >= 95 ? '优秀' : healthScore.value >= 80 ? '良好' : healthScore.value >= 50 ? '警告' : '异常')

const sysInfo = computed(() => { const s=systemStatus.value||{}; const u=s.users||{}; return {version:s.version||'--',uptime:s.uptime||'--',activeUsers:u.active||0,totalUsers:u.total||0} })
const dbInfo = computed(() => dbStatus.value || {})

const logColumns: DataTableColumn[] = [
  { title:"时间", key:"time", width:155, render:(_,r:any)=>fmtTime(r.created_at) },
  { title:"级别", key:"level", width:60, render:(_,r:any)=>{const lv=(r.log_level||r.level||'info').toLowerCase();return h('span',{class:`log-lv log-lv-${lv}`},lv.toUpperCase())} },
  { title:"消息", key:"msg", ellipsis:true, render:(_,r:any)=>r.details||r.action||r.message||'' },
]

// ---- methods ----
function thresholdColor(p:number){return p>=80?'#EF4444':p>=50?'#F59E0B':'#22C55E'}
function fmtBytes(b?:number):string{if(!b)return'0 B';return b>=1<<30?(b/(1<<30)).toFixed(1)+' GB':b>=1<<20?(b/(1<<20)).toFixed(1)+' MB':(b/1024).toFixed(0)+' KB'}
function fmtNum(n?:number):string{return n!=null?n.toLocaleString():'--'}
function fmtTime(ts?:string):string{if(!ts)return'--';return ts.replace('T',' ').slice(0,19)}

async function refreshAll(){
  loading.value=true;error.value=false
  try{
    const[resRes,connRes,sysRes,dbRes,logRes]=await Promise.all([
      systemAPI.getResources().catch(()=>null),
      systemAPI.getConnections().catch(()=>null),
      systemAPI.getSystemStatus().catch(()=>null),
      systemAPI.getDatabaseStatus().catch(()=>null),
      systemAPI.getSystemLogs({limit:10}).catch(()=>({logs:[]})),
    ])
    resourceUsage.value=resRes;connectionStatus.value=connRes;systemStatus.value=sysRes;dbStatus.value=dbRes
    recentLogs.value=(logRes as any)?.data||(logRes as any)?.logs||[]
    const r: any = resRes || {}; const now = new Date()
    cpuhistory.value.push({time:`${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`,cpu:r.cpu_percent??0,mem:r.memory_percent??0})
    if(cpuhistory.value.length>30)cpuhistory.value.shift()
    lastRefresh.value=now.toLocaleTimeString('zh-CN')
    await nextTick();updateTrendChart()
  }catch{error.value=true}finally{loading.value=false}
}

function initTrendChart(){
  if(!trendChartRef.value||trendChart)return
  trendChart=createChart(trendChartRef.value,{
    width:trendChartRef.value.clientWidth,
    height:trendChartRef.value.clientHeight||170,
    layout:{background:{type:ColorType.Solid,color:'transparent'},textColor:'#888',attributionLogo:false},
    grid:{vertLines:{color:'rgba(255,255,255,.06)'},horzLines:{color:'rgba(255,255,255,.06)'}},
    rightPriceScale:{borderVisible:false},
    timeScale:{borderVisible:false,timeVisible:true,secondsVisible:false},
    crosshair:{mode:0},
    handleScroll:false,handleScale:false,
  })
  cpuSeries=trendChart.addSeries(LineSeries,{color:'#22C55E',lineWidth:2,priceFormat:{type:'custom',formatter:(v:number)=>v.toFixed(1)+'%'}})
  memSeries=trendChart.addSeries(LineSeries,{color:'#3B82F6',lineWidth:2,priceFormat:{type:'custom',formatter:(v:number)=>v.toFixed(1)+'%'}})
  trendChart.timeScale().applyOptions({barSpacing:1.25})
}

function updateTrendChart(){
  if(cpuhistory.value.length<2)return;initTrendChart()
  if(!trendChart||!cpuSeries||!memSeries)return
  const base=Math.floor(Date.now()/1000)-cpuhistory.value.length*30
  cpuSeries.setData(cpuhistory.value.map((d,i)=>({time:(base+i*30) as any,value:d.cpu})))
  memSeries.setData(cpuhistory.value.map((d,i)=>({time:(base+i*30) as any,value:d.mem})))
  trendChart.timeScale().fitContent()
  trendChart.timeScale().applyOptions({barSpacing:1.25})
}

function handleResize(){if(trendChart&&trendChartRef.value)trendChart.applyOptions({width:trendChartRef.value.clientWidth,height:trendChartRef.value.clientHeight})}

onMounted(()=>{refreshAll();_timer=setInterval(refreshAll,30000);window.addEventListener('resize',handleResize)})
onUnmounted(()=>{if(_timer)clearInterval(_timer);window.removeEventListener('resize',handleResize);trendChart?.remove();trendChart=null})
</script>

<style scoped>
.dashboard{padding:0;padding-bottom:24px;height:100%;overflow-y:auto}
.refresh-time{font-size:12px;color:var(--n-text-color-3);margin-right:4px}
.row-equal{align-items:stretch}
.row-equal > :deep(.n-grid-item){display:flex}
.card-fill{flex:1;display:flex;flex-direction:column}
.card-fill > :deep(.n-card__content){flex:1}
.card-hdr{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600}

/* CPU card */
.res-grid{display:flex;align-items:center;gap:24px;padding:8px 4px}
.pct-num{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}
.pct-num small{font-size:13px;font-weight:400}
.res-stats{display:flex;flex-direction:column;gap:8px;flex:1}
.stat-line{display:flex;justify-content:space-between;font-size:12px}
.stat-k{color:var(--n-text-color-3)}
.stat-v{color:var(--n-text-color-2);font-weight:500}

/* 内存 & 磁盘 */
.dual-section{display:flex;flex-direction:column;gap:16px;padding:4px 0}
.section-block{display:flex;flex-direction:column;gap:6px}
.section-top{display:flex;align-items:center;gap:6px;font-size:13px;font-weight:500;color:var(--n-text-color-2)}
.section-val{margin-left:auto;font-weight:700;font-variant-numeric:tabular-nums;font-size:14px;color:var(--n-text-color-1)}
.section-sub{font-size:11px;color:var(--n-text-color-3)}

/* 健康 */
.health-layout{display:flex;align-items:center;gap:24px;padding:4px 0}
.hl-left{display:flex;flex-direction:column;align-items:center;min-width:72px}
.hl-score{font-size:42px;font-weight:700;line-height:1.1}
.hl-label{font-size:13px;color:var(--n-text-color-3);margin-top:2px}
.hl-status{font-size:13px;font-weight:600;margin-top:4px}
.hl-right{display:flex;flex-direction:column;gap:8px;flex:1}
.hl-conn{display:flex;align-items:center;gap:8px;font-size:12px}
.hl-cname{color:var(--n-text-color-2);min-width:52px}
.hl-cval{color:var(--n-text-color-3);margin-left:auto}

/* trend */
.trend-chart{width:100%;height:170px}

/* kv */
.kv-list{display:flex;flex-direction:column;gap:10px}
.kv-item{display:flex;justify-content:space-between}
.kv-key{font-size:12px;color:var(--n-text-color-3)}
.kv-val{font-size:13px;font-weight:500;color:var(--n-text-color-1)}

:deep(.log-lv){font-size:10px;font-weight:600;padding:1px 5px;border-radius:3px}
:deep(.log-lv-info){color:#3794ff;background:rgba(55,148,255,.12)}
:deep(.log-lv-warning){color:#d7ba7d;background:rgba(215,186,125,.12)}
:deep(.log-lv-error){color:#f44747;background:rgba(244,71,71,.12)}
:deep(.log-lv-debug){color:#999;background:rgba(153,153,153,.12)}

.stagger-enter-active{transition:all .4s var(--n-bezier)}
.stagger-enter-from{opacity:0;transform:translateY(24px)}
</style>
