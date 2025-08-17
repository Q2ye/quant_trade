<!--时间范围滑块-->
<template>
  <div class="time-range-slider">
    <div class="date-display">
      <span>{{ formatDate(localValue[0]) }}</span>
      <span>至</span>
      <span>{{ formatDate(localValue[1]) }}</span>
    </div>

    <div class="slider-container">
      <div class="slider-track">
        <div
          class="slider-range"
          :style="{
            left: `${startPercent}%`,
            right: `${100 - endPercent}%`
          }"
        />
      </div>

      <input
        type="range"
        class="slider-handle start-handle"
        :min="minTimestamp"
        :max="maxTimestamp"
        :value="localValue[0].getTime()"
        @input="handleStartChange"
      >

      <input
        type="range"
        class="slider-handle end-handle"
        :min="minTimestamp"
        :max="maxTimestamp"
        :value="localValue[1].getTime()"
        @input="handleEndChange"
      >
    </div>
  </div>
</template>

<script>
import dayjs from 'dayjs'

export default {
  name: "TimeRangeSlider",
  props: {
    minDate: {
      type: [String, Date],
      default: () => dayjs().subtract(5, 'year').toDate()
    },
    maxDate: {
      type: [String, Date],
      default: () => new Date()
    },
    value: {
      type: Array,
      default: () => [
        dayjs().subtract(1, 'year').toDate(),
        new Date()
      ]
    }
  },
  data() {
    return {
      localValue: [...this.value],
      dateFormat: 'YYYY-MM-DD'
    }
  },
  computed: {
    minTimestamp() {
      return new Date(this.minDate).getTime()
    },
    maxTimestamp() {
      return new Date(this.maxDate).getTime()
    },
    startPercent() {
      const range = this.maxTimestamp - this.minTimestamp
      return ((this.localValue[0].getTime() - this.minTimestamp) / range) * 100
    },
    endPercent() {
      const range = this.maxTimestamp - this.minTimestamp
      return 100 - ((this.maxTimestamp - this.localValue[1].getTime()) / range) * 100
    }
  },
  watch: {
    value(newVal) {
      this.localValue = [...newVal]
    }
  },
  methods: {
    formatDate(date) {
      return dayjs(date).format(this.dateFormat)
    },

    handleStartChange(e) {
      const timestamp = parseInt(e.target.value)
      const newDate = new Date(timestamp)
      if (newDate < this.localValue[1]) {
        this.localValue[0] = newDate
        this.emitChange()
      }
    },

    handleEndChange(e) {
      const timestamp = parseInt(e.target.value)
      const newDate = new Date(timestamp)
      if (newDate > this.localValue[0]) {
        this.localValue[1] = newDate
        this.emitChange()
      }
    },

    emitChange() {
      this.$emit('input', [...this.localValue])
      this.$emit('change', [...this.localValue])
    }
  }
}
</script>

<style scoped>
.time-range-slider {
  padding: 15px 10px;
}

.date-display {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-size: 14px;
  color: #606266;
}

.slider-container {
  position: relative;
  height: 30px;
}

.slider-track {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 4px;
  background-color: #dcdfe6;
  border-radius: 2px;
  transform: translateY(-50%);
}

.slider-range {
  position: absolute;
  height: 100%;
  background-color: #409eff;
  border-radius: 2px;
}

.slider-handle {
  position: absolute;
  top: 50%;
  width: 100%;
  height: 12px;
  margin: 0;
  transform: translateY(-50%);
  background: transparent;
  -webkit-appearance: none; /* Safari、Chrome 等webkit内核 */
  -moz-appearance: none;    /* Firefox 等Gecko内核 */
  appearance: none;         /* 标准属性，必须添加 */
  pointer-events: none;
  z-index: 2;
}

.slider-handle::-webkit-slider-thumb {
  pointer-events: auto;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #409eff;
  cursor: pointer;
  -webkit-appearance: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.slider-handle::-moz-range-thumb {
  pointer-events: auto;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #409eff;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
</style>