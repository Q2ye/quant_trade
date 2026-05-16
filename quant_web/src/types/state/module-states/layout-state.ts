// 布局状态管理
// 负责管理应用的整体布局、侧边栏、主题等界面状态

// 菜单项接口
export interface MenuItem {
  key: string;
  label: string;
  icon: string;
  children?: MenuItem[];
  path?: string;
}

// 标签页项接口
export interface TabItem {
  id: string;
  title: string;
  path: string;
  closable: boolean;
  props?: any;
}

// 预警项接口
export interface AlertItem {
  id: string;
  type: "success" | "info" | "warning" | "error";
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
}

// 观察列表项接口
export interface WatchlistItem {
  id: string;
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
}

// 快速操作项接口
export interface QuickActionItem {
  id: string;
  label: string;
  icon: string;
  action: string;
  confirm?: boolean;
}

// 顶部导航接口
export interface TopNavigation {
  logo: string;
  platformName: string;
  marketIndicators: any[];
  search: {
    placeholder: string;
    recentSearches: any[];
    hotSearches: any[];
  };
  notifications: any[];
  user: any;
  systemStatus: {
    connected: boolean;
    status: string;
    message: string;
  };
}

// 侧边导航接口
export interface SiderNavigation {
  collapsed: boolean;
  activeKey: string;
  openKeys: string[];
  menuItems: MenuItem[];
}

// 主工作区接口
export interface MainWorkspace {
  tabs: TabItem[];
  activeTab: string;
  tabHistory: string[];
}

// 右侧面板接口
export interface RightPanel {
  collapsed: boolean;
  alerts: AlertItem[];
  watchlist: WatchlistItem[];
  quickActions: QuickActionItem[];
}

export interface LayoutState {
  // 顶部导航栏状态
  topNavigation: TopNavigation;

  // 侧边栏状态
  siderNavigation: SiderNavigation;

  // 主工作区状态
  mainWorkspace: MainWorkspace;

  // 右侧面板状态
  rightPanel: RightPanel;

  // 主题配置
  theme: string;

  // 语言设置
  language: string;

  // 原有的布局状态（保持兼容）
  sidebar?: {
    collapsed: boolean;
    width: number;
    collapsedWidth: number;
  };

  header?: {
    height: number;
    fixed: boolean;
    showBreadcrumb: boolean;
  };

  tabs?: {
    enabled: boolean;
    list: Array<{
      id: string;
      title: string;
      path: string;
      closable: boolean;
    }>;
    activeTab: string;
  };

  themeConfig?: {
    mode: "light" | "dark";
    primaryColor: string;
    backgroundColor: string;
    fontFamily: string;
  };

  layoutMode?: "sidemenu" | "topmenu" | "mix";
  content?: {
    padding: number;
    backgroundColor: string;
  };
  settings?: {
    showSettings: boolean;
    fixedHeader: boolean;
    showTagsView: boolean;
    showSidebarLogo: boolean;
    showFooter: boolean;
  };
}
