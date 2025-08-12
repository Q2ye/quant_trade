<!--代码差异对比组件-->
<!-- src/components/strategy/CodeDiff.vue -->
<template>
  <div class="code-diff">
    <div class="diff-header">
      <div class="version">
        <i class="fas fa-file-code"></i>
        <span>{{ leftTitle }}</span>
      </div>
      <div class="version">
        <i class="fas fa-file-code"></i>
        <span>{{ rightTitle }}</span>
      </div>
    </div>

    <div class="diff-container">
      <div class="code-panel old-code">
        <div v-for="(line, index) in leftCode" :key="'left'+index"
             class="line"
             :class="{'removed': line.status === 'removed'}">
          <span class="line-number">{{ index + 1 }}</span>
          <span>{{ line.text }}</span>
        </div>
      </div>
      <div class="code-panel new-code">
        <div v-for="(line, index) in rightCode" :key="'right'+index"
             class="line"
             :class="{'added': line.status === 'added'}">
          <span class="line-number">{{ index + 1 }}</span>
          <span>{{ line.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "CodeDiff",
  props: {
    leftCode: {
      type: Array,
      required: true,
      default: () => []
    },
    rightCode: {
      type: Array,
      required: true,
      default: () => []
    },
    leftTitle: {
      type: String,
      default: "旧版本"
    },
    rightTitle: {
      type: String,
      default: "新版本"
    }
  }
};
</script>

<style scoped>
.code-diff {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.diff-header {
  display: flex;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
}

.diff-header .version {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 15px;
  font-weight: 500;
  color: #64b5f6;
}

.diff-header .version i {
  font-size: 1.2rem;
  color: #409eff;
}

.diff-container {
  display: flex;
  height: 300px;
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.code-panel {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
  position: relative;
}

.old-code {
  border-right: 1px solid rgba(64, 158, 255, 0.2);
}

.line {
  padding: 2px 5px;
  white-space: pre;
  display: flex;
}

.added {
  background: rgba(46, 160, 67, 0.2);
  border-left: 3px solid #2ea043;
}

.removed {
  background: rgba(248, 81, 73, 0.2);
  border-left: 3px solid #f85149;
}

.line-number {
  display: inline-block;
  width: 30px;
  color: #6b7280;
  text-align: right;
  margin-right: 15px;
  user-select: none;
}
</style>