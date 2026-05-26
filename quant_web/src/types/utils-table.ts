// 表格相关类型定义

/**
 * 表格列配置接口
 */
export interface TableColumn {
  prop: string; // 字段名
  label: string; // 列标题
  width?: number | string; // 列宽度
  minWidth?: number | string; // 最小宽度
  fixed?: "left" | "right"; // 固定列
  sortable?: boolean; // 是否可排序
  sortOrders?: Array<"asc" | "desc">; // 排序顺序
  resizable?: boolean; // 是否可调整宽度
  formatter?: (
    row: any,
    column: TableColumn,
    cellValue: any,
    index: number,
  ) => any; // 格式化函数
  align?: "left" | "center" | "right"; // 对齐方式
  headerAlign?: "left" | "center" | "right"; // 表头对齐方式
  className?: string; // 自定义类名
  labelClassName?: string; // 表头自定义类名
  showOverflowTooltip?: boolean; // 是否显示溢出提示
}

/**
 * 表格分页配置接口
 */
export interface TablePagination {
  currentPage: number; // 当前页码
  pageSize: number; // 每页大小
  total: number; // 总数
  pageSizes?: number[]; // 每页大小选项
  layout?: string; // 布局组件
  background?: boolean; // 是否有背景色
}

/**
 * 表格选择配置接口
 */
export interface TableSelection {
  type?: "checkbox" | "radio"; // 选择类型
  selectable?: (row: any, index: number) => boolean; // 是否可选
  reserveSelection?: boolean; // 是否保留选择
}

/**
 * 表格操作列配置接口
 */
export interface TableAction {
  name: string; // 操作名称
  label: string; // 显示文本
  type?: "primary" | "success" | "warning" | "danger" | "info"; // 按钮类型
  icon?: string; // 图标
  disabled?: (row: any) => boolean; // 是否禁用
  show?: (row: any) => boolean; // 是否显示
  onClick: (row: any, index: number) => void; // 点击事件
}

/**
 * 表格配置接口
 */
export interface TableConfig {
  columns: TableColumn[]; // 列配置
  data: any[]; // 表格数据
  pagination?: TablePagination; // 分页配置
  selection?: TableSelection; // 选择配置
  actions?: TableAction[]; // 操作列配置
  stripe?: boolean; // 是否显示斑马纹
  border?: boolean; // 是否显示边框
  showHeader?: boolean; // 是否显示表头
  highlightCurrentRow?: boolean; // 是否高亮当前行
  height?: number | string; // 表格高度
  maxHeight?: number | string; // 最大高度
  size?: "medium" | "small" | "mini"; // 表格尺寸
  loading?: boolean; // 加载状态
}

/**
 * 表格排序参数接口
 */
export interface TableSortParams {
  prop: string; // 排序字段
  order: "ascending" | "descending"; // 排序方向
}

/**
 * 表格过滤参数接口
 */
export interface TableFilterParams {
  [key: string]: any[]; // 过滤条件
}

/**
 * 表格事件接口
 */
export interface TableEvents {
  onSelect?: (selection: any[], row: any) => void; // 选择事件
  onSelectAll?: (selection: any[]) => void; // 全选事件
  onSelectionChange?: (selection: any[]) => void; // 选择变化事件
  onSortChange?: (sortParams: TableSortParams) => void; // 排序变化事件
  onFilterChange?: (filterParams: TableFilterParams) => void; // 过滤变化事件
  onRowClick?: (row: any, column: TableColumn, event: Event) => void; // 行点击事件
  onRowDblClick?: (row: any, column: TableColumn, event: Event) => void; // 行双击事件
  onCellClick?: (
    row: any,
    column: TableColumn,
    cell: any,
    event: Event,
  ) => void; // 单元格点击事件
}

/**
 * 表格搜索配置接口
 */
export interface TableSearchConfig {
  fields: Array<{
    prop: string; // 搜索字段
    label: string; // 搜索标签
    type?: "input" | "select" | "date" | "daterange"; // 搜索类型
    options?: Array<{ label: string; value: any }>; // 选项（用于select）
    placeholder?: string; // 占位符
  }>;
  showAdvanced?: boolean; // 是否显示高级搜索
  advancedFields?: TableSearchConfig["fields"]; // 高级搜索字段
}

/**
 * 表格导出配置接口
 */
export interface TableExportConfig {
  filename: string; // 导出文件名
  fields: Array<{
    prop: string; // 导出字段
    label: string; // 导出列标题
    formatter?: (value: any, row: any) => any; // 格式化函数
  }>;
  exportType?: "csv" | "excel"; // 导出类型
}
