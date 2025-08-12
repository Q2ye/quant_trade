// ECharts按需加载插件
import * as echarts from 'echarts/core';
import {BarChart, LineChart, PieChart, CandlestickChart, HeatmapChart} from 'echarts/charts';
import {
    GridComponent,
    TooltipComponent,
    LegendComponent,
    DataZoomComponent,
    VisualMapComponent
} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';

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
    CanvasRenderer
]);
export default {
    install(app) {
        app.config.globalProperties.$echarts = echarts;
    }
};