<template>
  <div class="stock-announcements">
    <div v-if="announcements.length === 0" class="empty">暂无公告数据</div>
    <el-timeline v-else>
      <el-timeline-item
        v-for="(item, index) in announcements"
        :key="index"
        :timestamp="item.time"
        placement="top"
      >
        <el-card>
          <div class="announcement-header">
            <span class="symbol">{{ item.symbol }}</span>
            <el-tag
              :type="getTagType(item.type)"
              size="small"
              class="tag"
            >
              {{ item.type }}
            </el-tag>
          </div>
          <p class="title">{{ item.title }}</p>
          <div class="actions">
            <el-button type="text" size="small">查看详情</el-button>
            <el-button type="text" size="small">加入收藏</el-button>
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

export default defineComponent({
  name: "StockAnnouncements",
  props: {
    announcements: Array
  },
  setup() {
    const getTagType = (type) => {
      switch(type) {
        case '利好': return 'danger';
        case '利空': return 'success';
        default: return 'info';
      }
    };

    return {
      getTagType
    };
  }
});
</script>

<style scoped>
.stock-announcements {
  height: 250px;
  overflow-y: auto;
  padding: 10px 5px;
}

.empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.announcement-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.symbol {
  font-weight: bold;
  color: #409EFF;
}

.tag {
  margin-left: 10px;
}

.title {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
}

.actions {
  margin-top: 8px;
  text-align: right;
}

.el-timeline {
  padding-left: 10px;
}

.el-timeline-item {
  padding-bottom: 15px;
}
</style>