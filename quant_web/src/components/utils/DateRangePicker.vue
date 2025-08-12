<!--日期选择器-->
<!-- src/components/utils/DateRangePicker.vue -->
<template>
  <div class="date-range-picker">
    <div class="date-input-group">
      <div class="date-input">
        <label for="startDate">开始日期：</label>
        <input
            type="date"
            v-model="startDate"
            :min="minDate"
            :max="endDate || maxDate"
            @change="handleDateChange"
        >
      </div>

      <div class="date-input">
        <label for="endDate">结束日期：</label>
        <input
            type="date"
            v-model="endDate"
            :min="startDate || minDate"
            :max="maxDate"
            @change="handleDateChange"
        >
      </div>
    </div>

    <div class="preview">
      <p>回测时间范围：<span>{{ formattedStartDate }} 至 {{ formattedEndDate }}</span></p>
      <p>总交易日数：<span>{{ tradingDays }}</span> 天</p>
    </div>

    <div class="quick-selection">
      <button
          v-for="period in quickPeriods"
          :key="period.value"
          @click="selectPeriod(period.value)"
          class="period-btn"
      >
        {{ period.label }}
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: "DateRangePicker",
  props: {
    minDate: {
      type: String,
      default: '2010-01-01'
    },
    maxDate: {
      type: String,
      default: () => new Date().toISOString().split('T')[0]
    },
    initialStartDate: String,
    initialEndDate: String
  },
  data() {
    return {
      startDate: this.initialStartDate || '2020-01-01',
      endDate: this.initialEndDate || new Date().toISOString().split('T')[0],
      quickPeriods: [
        {label: "最近1年", value: 1},
        {label: "最近3年", value: 3},
        {label: "最近5年", value: 5},
        {label: "全部数据", value: 'all'}
      ]
    };
  },
  computed: {
    formattedStartDate() {
      return this.formatDate(this.startDate);
    },
    formattedEndDate() {
      return this.formatDate(this.endDate);
    },
    tradingDays() {
      if (!this.startDate || !this.endDate) return 0;

      const start = new Date(this.startDate);
      const end = new Date(this.endDate);
      const diffTime = Math.abs(end - start);
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

      // 简单估算：每年约252个交易日
      const years = diffDays / 365;
      return Math.round(years * 252);
    }
  },
  methods: {
    formatDate(dateString) {
      if (!dateString) return '未选择';
      const date = new Date(dateString);
      return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      });
    },
    selectPeriod(years) {
      const endDate = new Date();
      const startDate = new Date();

      if (years === 'all') {
        this.startDate = this.minDate;
        this.endDate = this.maxDate;
      } else {
        startDate.setFullYear(endDate.getFullYear() - years);
        this.startDate = startDate.toISOString().split('T')[0];
        this.endDate = endDate.toISOString().split('T')[0];
      }

      this.emitDateChange();
    },
    handleDateChange() {
      this.emitDateChange();
    },
    emitDateChange() {
      this.$emit('date-change', {
        start: this.startDate,
        end: this.endDate,
        tradingDays: this.tradingDays
      });
    }
  }
};
</script>

<style scoped>
.date-range-picker {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.date-input-group {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-bottom: 20px;
}

.date-input {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-input label {
  min-width: 80px;
  color: #a8c7ff;
  font-size: 0.95rem;
}

.date-input input {
  flex: 1;
  padding: 10px 15px;
  background: rgba(24, 50, 90, 0.5);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #e0e7ff;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.3s;
}

.date-input input:focus {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.preview {
  padding: 15px;
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  font-size: 0.95rem;
  margin-bottom: 20px;
}

.preview p {
  margin-bottom: 8px;
}

.preview span {
  color: #64b5f6;
  font-weight: 500;
}

.quick-selection {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.period-btn {
  padding: 8px 15px;
  background: rgba(24, 50, 90, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #a8c7ff;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 0.9rem;
}

.period-btn:hover {
  background: rgba(64, 158, 255, 0.2);
  border-color: #409eff;
  color: #e0e7ff;
}
</style>