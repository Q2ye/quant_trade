// theme-loader.ts
export interface ThemeColors {
  'primary-bg': string;
  'secondary-bg': string;
  'accent-color': string;
  'text-primary': string;
  'text-secondary': string;
  'border-color': string;
  'success-color': string;
  'warning-color': string;
  'danger-color': string;
  'card-bg': string;
  'toolbar-bg': string;
  'sidebar-bg': string;
  'chart-bg': string;
  'chart-grid': string;
  'chart-up': string;
  'chart-down': string;
  'input-bg': string;
  'input-border': string;
  'hover-bg': string;
  'active-bg': string;
}

export interface Theme {
  name: string;
  type: 'light' | 'dark';
  colors: ThemeColors;
}

export interface ThemeConfig {
  currentTheme: string;
  themes: {
    [key: string]: Theme;
  };
  layout: {
    'sidebar-width': string;
    'sidebar-collapsed-width': string;
    'header-height': string;
    'footer-height': string;
    'chart-height': string;
    'chart-min-height': string;
  };
  typography: {
    'font-family': string;
    'font-size-base': string;
    'line-height-base': number;
    'font-weight-normal': number;
    'font-weight-medium': number;
    'font-weight-semibold': number;
    'font-weight-bold': number;
  };
  spacing: {
    spacer: string;
    spacers: {
      [key: string]: string;
    };
  };
  border: {
    'border-radius': string;
    'border-radius-lg': string;
    'border-radius-sm': string;
    'border-width': string;
  };
  animations: {
    'transition-fast': string;
    'transition-normal': string;
    'transition-slow': string;
    'hover-transform': string;
  };
}

class ThemeLoader {
  private currentTheme: string = 'quant-dark';
  private themes: { [key: string]: Theme } = {};
  private config: ThemeConfig | null = null;

  async loadTheme(): Promise<ThemeConfig> {
    try {
      const response = await fetch('/theme.json');
      this.config = await response.json();

      if (this.config) {
        this.themes = this.config.themes;
        this.currentTheme = this.config.currentTheme;

        this.applyTheme(this.currentTheme);
        return this.config;
      } else {
        throw new Error('Failed to load theme configuration');
      }
    } catch (error) {
      console.error('Failed to load theme:', error);
      this.applyFallbackTheme();
      // 创建一个新的错误并抛出，表明使用了 fallback 主题
      const fallbackError = new Error('Using fallback theme due to load failure');
      fallbackError.cause = error;
      throw fallbackError;
    }
  }

  applyTheme(themeName: string): void {
    const theme = this.themes[themeName];
    if (!theme) {
      console.warn(`Theme ${themeName} not found, using fallback`);
      this.applyFallbackTheme();
      return;
    }

    const root = document.documentElement;

    // 应用颜色变量
    Object.entries(theme.colors).forEach(([key, value]) => {
      root.style.setProperty(`--${key}`, value);
    });

    // 应用布局变量
    if (this.config) {
      Object.entries(this.config.layout).forEach(([key, value]) => {
        root.style.setProperty(`--${key}`, value);
      });

      // 应用字体变量
      Object.entries(this.config.typography).forEach(([key, value]) => {
        if (key !== 'spacers') {
          root.style.setProperty(`--${key}`, value.toString());
        }
      });

      // 应用间距变量
      Object.entries(this.config.spacing.spacers).forEach(([key, value]) => {
        root.style.setProperty(`--spacer-${key}`, value);
      });

      // 应用边框变量
      Object.entries(this.config.border).forEach(([key, value]) => {
        root.style.setProperty(`--${key}`, value);
      });

      // 应用动画变量
      Object.entries(this.config.animations).forEach(([key, value]) => {
        root.style.setProperty(`--${key}`, value);
      });
    }

    // 设置主题类型
    root.setAttribute('data-theme', theme.type);
    root.setAttribute('data-theme-name', themeName);

    // 触发主题变化事件
    document.dispatchEvent(new CustomEvent('themeChanged', {
      detail: { theme: themeName, themeData: theme }
    }));

    console.log(`Theme ${themeName} applied successfully`);
  }

  private applyFallbackTheme(): void {
    const fallbackTheme: ThemeColors = {
      'primary-bg': '#0D1117',
      'secondary-bg': '#161B22',
      'accent-color': '#2196F3',
      'text-primary': '#E6EDF3',
      'text-secondary': '#8B949E',
      'border-color': '#30363D',
      'success-color': '#3FB950',
      'warning-color': '#D29922',
      'danger-color': '#F85149',
      'card-bg': '#161B22',
      'toolbar-bg': '#161B22',
      'sidebar-bg': '#0D1117',
      'chart-bg': '#161B22',
      'chart-grid': '#30363D',
      'chart-up': '#3FB950',
      'chart-down': '#F85149',
      'input-bg': '#0D1117',
      'input-border': '#30363D',
      'hover-bg': '#21262D',
      'active-bg': '#1C6FEC'
    };

    const root = document.documentElement;
    Object.entries(fallbackTheme).forEach(([key, value]) => {
      root.style.setProperty(`--${key}`, value);
    });
  }

  getAvailableThemes(): Array<{ id: string; name: string; type: string }> {
    return Object.keys(this.themes).map(key => ({
      id: key,
      name: this.themes[key].name,
      type: this.themes[key].type
    }));
  }

  setTheme(themeName: string): boolean {
    if (this.themes[themeName]) {
      this.currentTheme = themeName;
      this.applyTheme(themeName);

      // 保存到 localStorage
      localStorage.setItem('preferred-theme', themeName);

      // 更新配置中的当前主题
      if (this.config) {
        this.config.currentTheme = themeName;
      }

      return true;
    }
    return false;
  }

  getCurrentTheme(): string {
    return this.currentTheme;
  }

  getThemeConfig(): ThemeConfig | null {
    return this.config;
  }

  // 监听系统主题变化
  watchSystemTheme(): void {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      const systemTheme = e.matches ? 'dark' : 'light';
      const savedTheme = localStorage.getItem('preferred-theme');

      // 如果没有手动设置主题，则跟随系统
      if (!savedTheme) {
        const availableThemes = this.getAvailableThemes();
        const systemThemeMatch = availableThemes.find(theme => theme.type === systemTheme);
        if (systemThemeMatch) {
          this.setTheme(systemThemeMatch.id);
        }
      }
    };

    mediaQuery.addEventListener('change', handleChange);
  }
}

// 创建全局实例
export const themeLoader = new ThemeLoader();

// Vue 插件
export const ThemePlugin = {
  install(app: any) {
    app.config.globalProperties.$theme = themeLoader;
    app.provide('theme', themeLoader);
  }
};

export default themeLoader;