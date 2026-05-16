import * as echarts from "echarts/core";
import {
  BarChart,
  LineChart,
  PieChart,
  CandlestickChart,
  HeatmapChart,
} from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { App } from "vue";

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  CandlestickChart,
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export default {
  install(app: App) {
    app.config.globalProperties.$echarts = echarts;
  },
};
