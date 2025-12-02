import {
  // 市场相关
  TrendingUp,
  TrendingDown,
  BarChart,
  PieChart,
  Analytics,

  // 交易相关
  Cash,
  Wallet,
  Card,
  SwapHorizontal,

  // 系统相关
  Settings,
  Person,
  LogOut,

  // 连接状态
  CloudDownload,
  CloudOffline,
  Wifi,

  // 性能
  Speedometer,
  Pulse,

  // 通知
  Notifications,
  Alert,

  // 设置
  Cog,
  
  // 状态相关
  CheckmarkCircle,
  AlertCircle,
  Warning,
  InformationCircle,

  // 新增图标
  CubeOutline,
  Time,
  ShieldCheckmark,
  ChevronDown,
  NotificationsOutline,
  SwapVertical,
  Grid,
  Sync,
  Cube,
  Copy,
  TrendingUpOutline,
  Flask,
  Options,
  Calendar,
  Basket,
  WalletOutline,
  Terminal,
  List,
  Eye,
  Ban,
  Trophy,
  AnalyticsOutline,
  Scale,
  Desktop,
  DocumentText,
  People,
  ChevronBack,
  ChevronForward,
  StatsChart,
  PeopleCircle,
  CashOutline,

  // 新增 Material 风格图标替代
  Play,
  Save,
  ArrowBack
} from '@vicons/ionicons5'

export const icons = {
  // 市场相关
  TrendingUp,
  TrendingDown,
  BarChart,
  PieChart,
  Analytics,

  // 交易相关
  Cash,
  Wallet,
  Card,
  SwapHorizontal,

  // 系统相关
  Settings,
  Person,
  LogOut,

  // 连接状态
  CloudDownload,
  CloudOffline,
  Wifi,

  // 性能
  Speedometer,
  Pulse,

  // 通知
  Notifications,
  Alert,

  // 设置
  Cog,

  // 状态相关
  CheckmarkCircle,
  AlertCircle,
  Warning,
  InformationCircle,

  // AppHeader 图标
  Robot: CubeOutline,
  Time,
  ShieldCheckmark,
  ChevronDown,

  // GlobalNotification 图标
  Bell: NotificationsOutline,
  NotificationsOutline,
  SwapVertical,

  // AppSidebar 图标
  Grid,
  Sync,
  Cube,
  Copy,
  TrendingUpOutline,
  Flask,
  Options,
  Calendar,
  Basket,
  WalletOutline,
  Terminal,
  List,
  Eye,
  Ban,
  Trophy,
  AnalyticsOutline,
  Scale,
  Puzzle: CubeOutline,
  Desktop,
  DocumentText,
  People,
  ChevronLeft: ChevronBack,
  ChevronRight: ChevronForward,

  // DashboardCard 图标
  StatsChart,
  PeopleCircle,
  CashOutline,

  // 新增图标
  PlayArrow:Play,
  Save,
  ArrowBack
}

// 类型定义
export type IconType = keyof typeof icons