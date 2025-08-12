<!--JSON数据查看器-->
<!-- src/components/utils/JsonViewer.vue -->
<template>
  <div class="json-viewer">
    <div class="json-container">
      <div v-for="(item, key) in jsonData" :key="key" class="json-line">
        <span class="key">"{{ key }}":</span>
        <span v-if="typeof item === 'string'" class="string">"{{ item }}"</span>
        <span v-else-if="typeof item === 'number'" class="number">{{ item }}</span>
        <span v-else-if="typeof item === 'boolean'" class="boolean">{{ item }}</span>
        <span v-else-if="item === null" class="null">null</span>
        <span v-else class="string">{{ item }}</span>
      </div>

      <template v-if="performanceMetrics">
        <div class="json-line">
          <span class="key">"performance_metrics":</span> {
        </div>
        <div v-for="(value, metric) in performanceMetrics" :key="metric" class="json-line indent">
          <span class="key">"{{ metric }}":</span>
          <span class="number">{{ value }}</span>,
        </div>
        <div class="json-line">}</div>
      </template>

      <template v-if="positions && positions.length">
        <div class="json-line">
          <span class="key">"positions":</span> [
        </div>
        <div v-for="(position, idx) in positions" :key="idx" class="json-line indent">
          {
          <span class="key">"symbol"</span>: <span class="string">"{{ position.symbol }}"</span>,
          <span class="key">"shares"</span>: <span class="number">{{ position.shares }}</span>,
          <span class="key">"avg_price"</span>: <span class="number">{{ position.avg_price }}</span>
          }{{ idx < positions.length - 1 ? ',' : '' }}
        </div>
        <div class="json-line">]</div>
      </template>
    </div>
  </div>
</template>

<script>
export default {
  name: "JsonViewer",
  props: {
    jsonData: {
      type: Object,
      default: () => ({})
    },
    performanceMetrics: {
      type: Object,
      default: null
    },
    positions: {
      type: Array,
      default: null
    }
  }
};
</script>

<style scoped>
.json-viewer {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.json-container {
  height: 300px;
  background: #0f172a;
  border-radius: 8px;
  padding: 15px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.json-line {
  white-space: nowrap;
}

.indent {
  padding-left: 20px;
}

.key {
  color: #ff79c6;
}

.string {
  color: #50fa7b;
}

.number {
  color: #bd93f9;
}

.boolean {
  color: #ffb86c;
}

.null {
  color: #ff5555;
}
</style>