// themes/naive-theme.ts
// 导入 Naive UI 的主题覆盖类型
import type {GlobalThemeOverrides} from 'naive-ui'

/**
 * 深色主题配置 - 量化交易专用深色主题
 * 基于原有 quant-dark 主题变量映射到 Naive UI 主题系统
 */
export const darkThemeOverrides: GlobalThemeOverrides = {
    // common 部分用于定义全局通用的主题变量
    common: {
        // ============================================================================
        // 基础颜色系统
        // ============================================================================

        // 主色调 - 使用原有的强调色
        // 主色调用于主要操作、按钮、链接等
        primaryColor: '#2196F3',                    // 主色调：Material Design 蓝色
        primaryColorHover: '#42A5F5',               // 主色调悬停状态：稍亮的蓝色
        primaryColorPressed: '#1976D2',             // 主色调按下状态：稍暗的蓝色
        primaryColorSuppl: '#1565C0',               // 主色调补充色：更深的蓝色

        // 基础背景色 - 映射原有 primary-bg 和 secondary-bg
        // 页面背景色：深色背景
        bodyColor: '#0D1117',                       // GitHub 深色主题背景色
        // 卡片背景色：稍亮的深色背景
        cardColor: '#161B22',                       // GitHub 深色主题卡片背景
        modalColor: '#161B22',                      // 模态框背景色：与卡片保持一致
        popoverColor: '#161B22',                    // 弹出层背景色：与卡片保持一致
        tableColor: '#161B22',                      // 表格背景色：与卡片保持一致
        tableHeaderColor: '#1A2230',                // 表头背景色：比卡片稍亮

        // 文字颜色系统 - 映射原有 text-primary 和 text-secondary
        textColorBase: '#E6EDF3',                   // 基础文字颜色：浅灰色
        textColor1: '#E6EDF3',                      // 主要文字颜色：用于正文
        textColor2: '#8B949E',                      // 次要文字颜色：用于辅助文本
        textColor3: '#6E7681',                      // 禁用文字颜色：用于不可用状态

        // 边框和分割线颜色 - 映射原有 border-color
        borderColor: '#30363D',                     // 边框颜色：深灰色
        dividerColor: '#30363D',                    // 分割线颜色：与边框保持一致

        // 悬停和激活状态背景色
        hoverColor: '#21262D',                      // 悬停背景色：元素悬停时的背景
        pressedColor: '#1C2128',                    // 按下背景色：元素被按下时的背景
        clearColor: 'rgba(255, 255, 255, 0)',       // 透明色：用于清除背景

        // ============================================================================
        // 圆角和阴影系统
        // ============================================================================

        // 圆角系统
        borderRadius: '6px',                        // 基础圆角：6px
        borderRadiusSmall: '4px',                   // 小圆角：4px，用于小元素

        // 阴影系统 - 映射原有 card-shadow 和 hover-shadow
        boxShadow1: '0 4px 12px rgba(0, 0, 0, 0.25)', // 基础阴影：轻微阴影
        boxShadow2: '0 8px 24px rgba(0, 0, 0, 0.35)', // 中等阴影：用于悬浮卡片
        boxShadow3: '0 16px 48px rgba(0, 0, 0, 0.45)', // 大阴影：用于模态框等

        // ============================================================================
        // 字体系统
        // ============================================================================
        fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif", // 字体族：现代无衬线字体
        fontFamilyMono: 'Monaco, "Courier New", monospace' // 等宽字体：代码编辑器字体
    },

    // ============================================================================
    // 按钮组件主题配置
    // ============================================================================
    Button: {
        // 高度配置 - 使用原有 button-height 变量
        heightMedium: '32px',                       // 中等按钮高度：32px
        heightSmall: '28px',                        // 小按钮高度：28px
        heightTiny: '24px',                         // 超小按钮高度：24px
        heightLarge: '36px',                        // 大按钮高度：36px

        // 圆角配置
        borderRadiusMedium: '6px',                  // 中等按钮圆角：6px
        borderRadiusSmall: '4px',                   // 小按钮圆角：4px

        // 主要按钮颜色
        colorPrimary: '#2196F3',                    // 主要按钮背景色：蓝色
        colorHoverPrimary: '#42A5F5',               // 主要按钮悬停背景色：亮蓝色
        colorPressedPrimary: '#1976D2',             // 主要按钮按下背景色：深蓝色
        colorFocusPrimary: '#2196F3',               // 主要按钮聚焦背景色：蓝色
        colorDisabledPrimary: 'rgba(33, 150, 243, 0.5)', // 主要按钮禁用背景色：半透明蓝色

        // 主要按钮文字颜色
        textColorPrimary: '#FFFFFF',                // 主要按钮文字颜色：白色
        textColorHoverPrimary: '#FFFFFF',           // 主要按钮悬停文字颜色：白色
        textColorPressedPrimary: '#FFFFFF',         // 主要按钮按下文字颜色：白色
        textColorFocusPrimary: '#FFFFFF',           // 主要按钮聚焦文字颜色：白色
        textColorDisabledPrimary: 'rgba(255, 255, 255, 0.5)', // 主要按钮禁用文字颜色：半透明白色

        // 主要按钮边框颜色
        borderPrimary: '1px solid #2196F3',         // 主要按钮边框：蓝色
        borderHoverPrimary: '1px solid #42A5F5',    // 主要按钮悬停边框：亮蓝色
        borderPressedPrimary: '1px solid #1976D2',  // 主要按钮按下边框：深蓝色
        borderFocusPrimary: '1px solid #2196F3',    // 主要按钮聚焦边框：蓝色

        // 次要按钮样式（使用 info 类型）
        colorInfo: '#161B22',                       // 次要按钮背景色：深灰色
        colorHoverInfo: '#21262D',                  // 次要按钮悬停背景色：稍亮深灰色
        colorPressedInfo: '#1A2230',                // 次要按钮按下背景色：深灰色
        borderInfo: '1px solid #30363D',            // 次要按钮边框：灰色边框
        borderHoverInfo: '1px solid #2196F3'        // 次要按钮悬停边框：蓝色边框
    },

    // ============================================================================
    // 卡片组件主题配置
    // ============================================================================
    Card: {
        color: '#161B22',                           // 卡片背景色：深灰色
        colorModal: '#161B22',                      // 模态框卡片背景色：深灰色
        borderRadius: '6px',                        // 卡片圆角：6px
        titleTextColor: '#E6EDF3',                  // 卡片标题文字颜色：浅灰色
        textColor: '#E6EDF3',                       // 卡片内容文字颜色：浅灰色
        borderColor: '#30363D',                     // 卡片边框颜色：灰色
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)' // 卡片阴影：轻微阴影
    },

    // ============================================================================
    // 数据表格组件主题配置
    // ============================================================================
    DataTable: {
        // 背景色配置
        thColor: '#1A2230',                         // 表头背景色：深蓝色
        thColorHover: '#21262D',                    // 表头悬停背景色：深灰色
        tdColor: '#161B22',                         // 表格主体背景色：深灰色
        tdColorHover: '#21262D',                    // 表格行悬停背景色：稍亮深灰色
        tdColorStriped: 'rgba(22, 27, 34, 0.8)',    // 斑马纹背景色：半透明深灰色

        // 文字颜色配置
        thTextColor: '#E6EDF3',                     // 表头文字颜色：浅灰色
        tdTextColor: '#E6EDF3',                     // 表格主体文字颜色：浅灰色

        // 边框配置
        borderColor: '#30363D',                     // 表格边框颜色：灰色
        thBorderColor: '#30363D',                   // 表头边框颜色：灰色
        tdBorderColor: '#30363D',                   // 单元格边框颜色：灰色

        // 其他配置
        borderRadius: '6px',                        // 表格圆角：6px
        paginationMargin: '16px 0 0 0'              // 分页器外边距：上16px，其他方向0
    },

    // ============================================================================
    // 输入框组件主题配置
    // ============================================================================
    Input: {
        // 背景色配置 - 映射原有 input-bg
        color: '#0D1117',                           // 输入框背景色：深色背景
        colorFocus: '#0D1117',                      // 输入框聚焦背景色：深色背景
        colorDisabled: 'rgba(13, 17, 23, 0.6)',     // 输入框禁用背景色：半透明深色

        // 边框配置
        border: '1px solid #30363D',                // 输入框边框：灰色边框
        borderFocus: '1px solid #2196F3',           // 输入框聚焦边框：蓝色边框
        borderHover: '1px solid #424a53',           // 输入框悬停边框：稍亮灰色
        borderDisabled: '1px solid rgba(48, 54, 61, 0.6)', // 输入框禁用边框：半透明灰色

        // 圆角配置
        borderRadius: '4px',                        // 输入框圆角：4px

        // 文字颜色配置
        textColor: '#E6EDF3',                       // 输入框文字颜色：浅灰色
        textColorDisabled: 'rgba(230, 237, 243, 0.6)', // 输入框禁用文字颜色：半透明白色
        placeholderColor: '#8B949E',                // 占位符文字颜色：灰色
        placeholderColorDisabled: 'rgba(139, 148, 158, 0.6)', // 禁用占位符文字颜色：半透明灰色

        // 聚焦状态光晕效果
        boxShadowFocus: '0 0 0 2px rgba(33, 150, 243, 0.2)', // 聚焦光晕：蓝色发光效果
        caretColor: '#2196F3'                       // 输入光标颜色：蓝色
    },

    // ============================================================================
    // 选择器组件主题配置
    // ============================================================================
    Select: {
        // 背景色配置
        color: '#0D1117',                           // 选择器背景色：深色背景
        colorFocus: '#0D1117',                      // 选择器聚焦背景色：深色背景
        colorDisabled: 'rgba(13, 17, 23, 0.6)',     // 选择器禁用背景色：半透明深色

        // 边框配置
        border: '1px solid #30363D',                // 选择器边框：灰色边框
        borderFocus: '1px solid #2196F3',           // 选择器聚焦边框：蓝色边框
        borderHover: '1px solid #424a53',           // 选择器悬停边框：稍亮灰色
        borderDisabled: '1px solid rgba(48, 54, 61, 0.6)', // 选择器禁用边框：半透明灰色

        // 圆角配置
        borderRadius: '4px',                        // 选择器圆角：4px

        // 文字颜色配置
        textColor: '#E6EDF3',                       // 选择器文字颜色：浅灰色
        placeholderColor: '#8B949E',                // 占位符文字颜色：灰色

        // 箭头图标颜色
        arrowColor: '#8B949E',                      // 下拉箭头颜色：灰色

        // 下拉菜单内部选择器样式
        peers: {
            InternalSelection: {
                textColor: '#E6EDF3'                // 内部选择器文字颜色：浅灰色
            }
        }
    },

    // ============================================================================
    // 消息组件主题配置
    // ============================================================================
    Message: {
        // 基础消息样式
        color: '#161B22',                           // 消息背景色：深灰色
        textColor: '#E6EDF3',                       // 消息文字颜色：浅灰色
        borderRadius: '6px',                        // 消息圆角：6px
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)', // 消息阴影：轻微阴影
        border: '1px solid #30363D',                // 消息边框：灰色边框

        // 成功消息样式 - 使用原有 success-color
        colorSuccess: 'rgba(103, 194, 58, 0.1)',    // 成功消息背景色：浅绿色半透明
        borderSuccess: '1px solid rgba(103, 194, 58, 0.3)', // 成功消息边框：绿色边框
        textColorSuccess: '#67c23a',                // 成功消息文字颜色：绿色
        iconColorSuccess: '#67c23a',                // 成功消息图标颜色：绿色

        // 信息消息样式 - 使用原有 info-color
        colorInfo: 'rgba(23, 162, 184, 0.1)',       // 信息消息背景色：浅蓝色半透明
        borderInfo: '1px solid rgba(23, 162, 184, 0.3)', // 信息消息边框：蓝色边框
        textColorInfo: '#17a2b8',                   // 信息消息文字颜色：蓝色
        iconColorInfo: '#17a2b8',                   // 信息消息图标颜色：蓝色

        // 警告消息样式 - 使用原有 warning-color
        colorWarning: 'rgba(210, 153, 34, 0.1)',    // 警告消息背景色：浅黄色半透明
        borderWarning: '1px solid rgba(210, 153, 34, 0.3)', // 警告消息边框：黄色边框
        textColorWarning: '#D29922',                // 警告消息文字颜色：黄色
        iconColorWarning: '#D29922',                // 警告消息图标颜色：黄色

        // 错误消息样式 - 使用原有 danger-color
        colorError: 'rgba(245, 108, 108, 0.1)',     // 错误消息背景色：浅红色半透明
        borderError: '1px solid rgba(245, 108, 108, 0.3)', // 错误消息边框：红色边框
        textColorError: '#f56c6c',                  // 错误消息文字颜色：红色
        iconColorError: '#f56c6c'                   // 错误消息图标颜色：红色
    },

    // ============================================================================
    // 通知组件主题配置
    // ============================================================================
    Notification: {
        // 基础通知样式
        color: '#161B22',                           // 通知背景色：深灰色
        textColor: '#E6EDF3',                       // 通知文字颜色：浅灰色
        borderRadius: '6px',                        // 通知圆角：6px
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)', // 通知阴影：中等阴影
        border: '1px solid #30363D',                // 通知边框：灰色边框
        titleTextColor: '#E6EDF3',                  // 通知标题文字颜色：浅灰色
        closeColor: '#8B949E',                      // 关闭按钮颜色：灰色
        closeColorHover: '#E6EDF3',                 // 关闭按钮悬停颜色：浅灰色
        closeColorPressed: '#FFFFFF'                // 关闭按钮按下颜色：白色
    },

    // ============================================================================
    // 对话框组件主题配置
    // ============================================================================
    Dialog: {
        // 对话框样式
        color: '#161B22',                           // 对话框背景色：深灰色
        textColor: '#E6EDF3',                       // 对话框文字颜色：浅灰色
        borderRadius: '6px',                        // 对话框圆角：6px
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)', // 对话框阴影：中等阴影
        border: '1px solid #30363D',                // 对话框边框：灰色边框
        titleTextColor: '#E6EDF3',                  // 对话框标题文字颜色：浅灰色
        iconColor: '#2196F3'                        // 对话框图标颜色：蓝色
    },

    // ============================================================================
    // 加载组件主题配置
    // ============================================================================
    Spin: {
        color: '#2196F3'                            // 加载指示器颜色：蓝色
    },

    // ============================================================================
    // 模态框组件主题配置
    // ============================================================================
    Modal: {
        // 模态框样式
        color: '#161B22',                           // 模态框背景色：深灰色
        textColor: '#E6EDF3',                       // 模态框文字颜色：浅灰色
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)', // 模态框阴影：中等阴影
        titleTextColor: '#E6EDF3'                   // 模态框标题文字颜色：浅灰色
    },

    // ============================================================================
    // 分页组件主题配置
    // ============================================================================
    Pagination: {
        // 分页项样式
        itemColor: '#161B22',                       // 分页项背景色：深灰色
        itemColorHover: '#21262D',                  // 分页项悬停背景色：稍亮深灰色
        itemColorPressed: '#21262D',                // 分页项按下背景色：稍亮深灰色
        itemColorActive: '#2196F3',                 // 当前页背景色：蓝色
        itemColorDisabled: 'rgba(22, 27, 34, 0.6)', // 禁用分页项背景色：半透明深灰色

        // 分页项边框
        itemBorder: '1px solid #30363D',            // 分页项边框：灰色边框
        itemBorderHover: '1px solid #2196F3',       // 分页项悬停边框：蓝色边框
        itemBorderPressed: '1px solid #1976D2',     // 分页项按下边框：深蓝色边框
        itemBorderActive: '1px solid #2196F3',      // 当前页边框：蓝色边框
        itemBorderDisabled: '1px solid rgba(48, 54, 61, 0.6)', // 禁用分页项边框：半透明灰色边框

        // 分页项文字颜色
        itemTextColor: '#E6EDF3',                   // 分页项文字颜色：浅灰色
        itemTextColorHover: '#2196F3',              // 分页项悬停文字颜色：蓝色
        itemTextColorPressed: '#1976D2',            // 分页项按下文字颜色：深蓝色
        itemTextColorActive: '#FFFFFF',             // 当前页文字颜色：白色
        itemTextColorDisabled: 'rgba(230, 237, 243, 0.6)', // 禁用分页项文字颜色：半透明白色

        // 跳转输入框样式
        inputColor: '#0D1117',                      // 跳转输入框背景色：深色背景
        inputBorder: '1px solid #30363D',           // 跳转输入框边框：灰色边框
        inputTextColor: '#E6EDF3'                   // 跳转输入框文字颜色：浅灰色
    },

    // ============================================================================
    // 标签组件主题配置
    // ============================================================================
    Tag: {
        // 基础标签样式
        color: '#21262D',                           // 标签背景色：深灰色
        colorHover: '#21262D',                      // 标签悬停背景色：深灰色
        colorPressed: '#21262D',                    // 标签按下背景色：深灰色
        border: '1px solid #30363D',                // 标签边框：灰色边框
        borderHover: '1px solid #2196F3',           // 标签悬停边框：蓝色边框
        borderPressed: '1px solid #1976D2',         // 标签按下边框：深蓝色边框
        textColor: '#E6EDF3',                       // 标签文字颜色：浅灰色
        textColorHover: '#2196F3',                  // 标签悬停文字颜色：蓝色
        textColorPressed: '#1976D2',                // 标签按下文字颜色：深蓝色
        borderRadius: '4px',                        // 标签圆角：4px

        // 成功标签样式
        colorSuccess: 'rgba(103, 194, 58, 0.1)',    // 成功标签背景色：浅绿色半透明
        borderSuccess: '1px solid rgba(103, 194, 58, 0.3)', // 成功标签边框：绿色边框
        textColorSuccess: '#67c23a',                // 成功标签文字颜色：绿色

        // 警告标签样式
        colorWarning: 'rgba(210, 153, 34, 0.1)',    // 警告标签背景色：浅黄色半透明
        borderWarning: '1px solid rgba(210, 153, 34, 0.3)', // 警告标签边框：黄色边框
        textColorWarning: '#D29922',                // 警告标签文字颜色：黄色

        // 错误标签样式
        colorError: 'rgba(245, 108, 108, 0.1)',     // 错误标签背景色：浅红色半透明
        borderError: '1px solid rgba(245, 108, 108, 0.3)', // 错误标签边框：红色边框
        textColorError: '#f56c6c',                  // 错误标签文字颜色：红色

        // 信息标签样式
        colorInfo: 'rgba(23, 162, 184, 0.1)',       // 信息标签背景色：浅蓝色半透明
        borderInfo: '1px solid rgba(23, 162, 184, 0.3)', // 信息标签边框：蓝色边框
        textColorInfo: '#17a2b8'                    // 信息标签文字颜色：蓝色
    },

    // ============================================================================
    // 开关组件主题配置
    // ============================================================================
    Switch: {
        // 开关轨道样式
        railColor: '#30363D',                       // 关闭状态轨道颜色：灰色
        railColorActive: '#2196F3',                 // 开启状态轨道颜色：蓝色
        railColorHover: '#424a53',                  // 轨道悬停颜色：稍亮灰色
        railColorActiveHover: '#42A5F5',            // 开启状态轨道悬停颜色：亮蓝色

        // 开关按钮样式
        buttonColor: '#8B949E',                     // 关闭状态按钮颜色：灰色
        buttonColorActive: '#FFFFFF',               // 开启状态按钮颜色：白色
        buttonColorHover: '#E6EDF3',                // 按钮悬停颜色：浅灰色
        buttonColorActiveHover: '#FFFFFF',          // 开启状态按钮悬停颜色：白色

        // 加载状态颜色
        loadingColor: '#2196F3',                    // 加载指示器颜色：蓝色
        boxShadowFocus: '0 0 0 2px rgba(33, 150, 243, 0.2)' // 聚焦状态阴影：蓝色发光效果
    },

    // ============================================================================
    // 滑动输入条组件主题配置
    // ============================================================================
    Slider: {
        // 轨道样式
        railColor: '#30363D',                       // 轨道背景色：灰色
        railColorHover: '#424a53',                  // 轨道悬停背景色：稍亮灰色

        // 填充轨道样式
        fillColor: '#2196F3',                       // 填充轨道颜色：蓝色
        fillColorHover: '#42A5F5',                  // 填充轨道悬停颜色：亮蓝色

        // 手柄样式
        handleColor: '#2196F3',                     // 手柄颜色：蓝色
        handleColorHover: '#42A5F5',                // 手柄悬停颜色：亮蓝色
        handleColorPressed: '#1976D2',              // 手柄按下颜色：深蓝色

        // 标记样式
        markTextColor: '#8B949E'                    // 标记文字颜色：灰色
    },

    // ============================================================================
    // 进度条组件主题配置
    // ============================================================================
    Progress: {
        // 轨道样式
        railColor: '#30363D',                       // 轨道背景色：灰色

        // 填充颜色 - 使用语义化颜色
        color: '#2196F3',                           // 默认进度颜色：蓝色
        colorSuccess: '#67c23a',                    // 成功进度颜色：绿色
        colorWarning: '#D29922',                    // 警告进度颜色：黄色
        colorError: '#f56c6c',                      // 错误进度颜色：红色
        colorInfo: '#17a2b8',                       // 信息进度颜色：蓝色

        // 文字颜色
        textColor: '#E6EDF3'                        // 进度文字颜色：浅灰色
    },

    // ============================================================================
    // 菜单组件主题配置
    // ============================================================================
    Menu: {
        // 菜单项样式
        itemColor: '#161B22',                       // 菜单项背景色：深灰色
        itemColorHover: '#21262D',                  // 菜单项悬停背景色：稍亮深灰色
        itemColorActive: 'rgba(33, 150, 243, 0.1)', // 菜单项激活背景色：蓝色半透明
        itemColorActiveHover: 'rgba(33, 150, 243, 0.15)', // 菜单项激活悬停背景色：更深的蓝色半透明
        itemColorActiveCollapsed: 'rgba(33, 150, 243, 0.1)', // 折叠状态激活背景色：蓝色半透明

        // 菜单项文字颜色
        itemTextColor: '#E6EDF3',                   // 菜单项文字颜色：浅灰色
        itemTextColorHover: '#2196F3',              // 菜单项悬停文字颜色：蓝色
        itemTextColorActive: '#2196F3',             // 菜单项激活文字颜色：蓝色
        itemTextColorChildActive: '#2196F3',        // 子菜单激活文字颜色：蓝色
        itemTextColorHorizontal: '#E6EDF3',         // 水平菜单文字颜色：浅灰色
        itemTextColorHoverHorizontal: '#2196F3',    // 水平菜单悬停文字颜色：蓝色
        itemTextColorActiveHorizontal: '#2196F3',   // 水平菜单激活文字颜色：蓝色

        // 菜单项图标颜色
        itemIconColor: '#8B949E',                   // 菜单项图标颜色：灰色
        itemIconColorHover: '#2196F3',              // 菜单项图标悬停颜色：蓝色
        itemIconColorActive: '#2196F3',             // 菜单项图标激活颜色：蓝色
        itemIconColorChildActive: '#2196F3',        // 子菜单图标激活颜色：蓝色
        itemIconColorHorizontal: '#8B949E',         // 水平菜单图标颜色：灰色
        itemIconColorHoverHorizontal: '#2196F3',    // 水平菜单图标悬停颜色：蓝色
        itemIconColorActiveHorizontal: '#2196F3',   // 水平菜单图标激活颜色：蓝色

        // 分组标题样式
        groupTextColor: '#8B949E',                  // 分组标题文字颜色：灰色

        // 箭头样式
        arrowColor: '#8B949E',                      // 箭头颜色：灰色
        arrowColorHover: '#2196F3',                 // 箭头悬停颜色：蓝色
        arrowColorActive: '#2196F3',                // 箭头激活颜色：蓝色
        arrowColorChildActive: '#2196F3',           // 子菜单箭头激活颜色：蓝色

        // 边框样式
        borderColor: '#30363D'                      // 菜单边框颜色：灰色
    },

    // ============================================================================
    // 布局组件主题配置
    // ============================================================================
    Layout: {
        // 布局颜色
        color: '#0D1117',                           // 布局背景色：深色背景
        colorEmbedded: '#161B22'                    // 嵌入布局背景色：深灰色
    },

    // ============================================================================
    // 加载条组件主题配置
    // ============================================================================
    LoadingBar: {
        colorLoading: '#2196F3'                     // 加载条颜色：蓝色
    }
}

/**
 * 浅色主题配置 - 量化交易专用浅色主题
 * 基于原有 quant-light 主题变量映射到 Naive UI 主题系统
 */
export const lightThemeOverrides: GlobalThemeOverrides = {
    // common 部分用于定义全局通用的主题变量
    common: {
        // ============================================================================
        // 基础颜色系统
        // ============================================================================

        // 主色调 - 保持与深色主题一致
        primaryColor: '#2196F3',                    // 主色调：Material Design 蓝色
        primaryColorHover: '#42A5F5',               // 主色调悬停状态：稍亮的蓝色
        primaryColorPressed: '#1976D2',             // 主色调按下状态：稍暗的蓝色
        primaryColorSuppl: '#1565C0',               // 主色调补充色：更深的蓝色

        // 基础背景色 - 映射原有浅色主题背景
        bodyColor: '#FFFFFF',                       // 页面背景色：白色
        cardColor: '#FFFFFF',                       // 卡片背景色：白色
        modalColor: '#FFFFFF',                      // 模态框背景色：白色
        popoverColor: '#FFFFFF',                    // 弹出层背景色：白色
        tableColor: '#FFFFFF',                      // 表格背景色：白色
        tableHeaderColor: '#F8FAFC',                // 表头背景色：浅灰色

        // 文字颜色系统 - 映射原有浅色主题文字颜色
        textColorBase: '#212529',                   // 基础文字颜色：深灰色
        textColor1: '#212529',                      // 主要文字颜色：深灰色
        textColor2: '#6C757D',                      // 次要文字颜色：中等灰色
        textColor3: '#8B949E',                      // 禁用文字颜色：浅灰色

        // 边框和分割线颜色 - 映射原有浅色主题边框
        borderColor: '#DEE2E6',                     // 边框颜色：浅灰色
        dividerColor: '#DEE2E6',                    // 分割线颜色：浅灰色

        // 悬停和激活状态背景色
        hoverColor: '#E9ECEF',                      // 悬停背景色：非常浅的灰色
        pressedColor: '#DEE2E6',                    // 按下背景色：浅灰色
        clearColor: 'rgba(255, 255, 255, 0)',       // 透明色：用于清除背景

        // ============================================================================
        // 圆角和阴影系统
        // ============================================================================

        // 圆角系统
        borderRadius: '4px',                        // 基础圆角：4px
        borderRadiusSmall: '2px',                   // 小圆角：2px

        // 阴影系统 - 映射原有浅色主题阴影
        boxShadow1: '0 4px 12px rgba(0, 0, 0, 0.08)', // 基础阴影：轻微阴影
        boxShadow2: '0 8px 24px rgba(0, 0, 0, 0.12)', // 中等阴影：用于悬浮卡片
        boxShadow3: '0 16px 48px rgba(0, 0, 0, 0.16)', // 大阴影：用于模态框等

        // ============================================================================
        // 字体系统
        // ============================================================================
        fontFamily: "'Inter', 'Segoe UI', sans-serif", // 字体族：现代无衬线字体
        fontFamilyMono: 'Monaco, "Courier New", monospace', // 等宽字体：代码编辑器字体
    },

    // ============================================================================
    // 按钮组件主题配置
    // ============================================================================
    Button: {
        heightMedium: '32px',                       // 中等按钮高度：32px
        heightSmall: '28px',                        // 小按钮高度：28px
        heightTiny: '24px',                         // 超小按钮高度：24px
        heightLarge: '36px',                        // 大按钮高度：36px
        borderRadiusMedium: '4px',                  // 中等按钮圆角：4px
        borderRadiusSmall: '2px',                   // 小按钮圆角：2px
        colorPrimary: '#2196F3',                    // 主要按钮背景色：蓝色
        colorHoverPrimary: '#42A5F5',               // 主要按钮悬停背景色：亮蓝色
        colorPressedPrimary: '#1976D2',             // 主要按钮按下背景色：深蓝色
        // 次要按钮样式
        colorInfo: '#F8F9FA',                       // 次要按钮背景色：浅灰色
        colorHoverInfo: '#E9ECEF',                  // 次要按钮悬停背景色：稍深的浅灰色
        colorPressedInfo: '#DEE2E6',                // 次要按钮按下背景色：浅灰色
        borderInfo: '1px solid #DEE2E6',            // 次要按钮边框：浅灰色边框
        borderHoverInfo: '1px solid #2196F3'        // 次要按钮悬停边框：蓝色边框
    },

    // ============================================================================
    // 卡片组件主题配置
    // ============================================================================
    Card: {
        color: '#FFFFFF',                           // 卡片背景色：白色
        colorModal: '#FFFFFF',                      // 模态框卡片背景色：白色
        borderRadius: '4px',                        // 卡片圆角：4px
        titleTextColor: '#212529',                  // 卡片标题文字颜色：深灰色
        textColor: '#212529',                       // 卡片内容文字颜色：深灰色
        borderColor: '#DEE2E6',                     // 卡片边框颜色：浅灰色
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)' // 卡片阴影：轻微阴影
    },

    // ============================================================================
    // 数据表格组件主题配置
    // ============================================================================
    DataTable: {
        thColor: '#F8FAFC',                         // 表头背景色：浅灰色
        thColorHover: '#E9ECEF',                    // 表头悬停背景色：稍深的浅灰色
        tdColor: '#FFFFFF',                         // 表格主体背景色：白色
        tdColorHover: '#E9ECEF',                    // 表格行悬停背景色：浅灰色
        tdColorStriped: 'rgba(248, 249, 250, 0.8)', // 斑马纹背景色：半透明浅灰色
        thTextColor: '#212529',                     // 表头文字颜色：深灰色
        tdTextColor: '#212529',                     // 表格主体文字颜色：深灰色
        borderColor: '#DEE2E6',                     // 表格边框颜色：浅灰色
        thBorderColor: '#DEE2E6',                   // 表头边框颜色：浅灰色
        tdBorderColor: '#DEE2E6',                   // 单元格边框颜色：浅灰色
        borderRadius: '4px'                         // 表格圆角：4px
    },

    // ============================================================================
    // 输入框组件主题配置
    // ============================================================================
    Input: {
        color: '#FFFFFF',                           // 输入框背景色：白色
        colorFocus: '#FFFFFF',                      // 输入框聚焦背景色：白色
        colorDisabled: 'rgba(255, 255, 255, 0.6)',  // 输入框禁用背景色：半透明白色
        border: '1px solid #DEE2E6',                // 输入框边框：浅灰色边框
        borderFocus: '1px solid #2196F3',           // 输入框聚焦边框：蓝色边框
        borderHover: '1px solid #adb5bd',           // 输入框悬停边框：灰色边框
        borderDisabled: '1px solid rgba(222, 226, 230, 0.6)', // 输入框禁用边框：半透明浅灰色
        borderRadius: '4px',                        // 输入框圆角：4px
        textColor: '#212529',                       // 输入框文字颜色：深灰色
        textColorDisabled: 'rgba(33, 37, 41, 0.6)', // 输入框禁用文字颜色：半透明深灰色
        placeholderColor: '#6C757D',                // 占位符文字颜色：中等灰色
        placeholderColorDisabled: 'rgba(108, 117, 125, 0.6)', // 禁用占位符文字颜色：半透明中等灰色
        boxShadowFocus: '0 0 0 2px rgba(33, 150, 243, 0.2)', // 聚焦光晕：蓝色发光效果
        caretColor: '#2196F3'                       // 输入光标颜色：蓝色
    },

    // ============================================================================
    // 消息组件主题配置
    // ============================================================================
    Message: {
        color: '#FFFFFF',                           // 消息背景色：白色
        textColor: '#212529',                       // 消息文字颜色：深灰色
        borderRadius: '4px',                        // 消息圆角：4px
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)', // 消息阴影：轻微阴影
        border: '1px solid #DEE2E6',                // 消息边框：浅灰色边框
        colorSuccess: 'rgba(40, 167, 69, 0.1)',     // 成功消息背景色：浅绿色半透明
        borderSuccess: '1px solid rgba(40, 167, 69, 0.3)', // 成功消息边框：绿色边框
        textColorSuccess: '#28A745',                // 成功消息文字颜色：绿色
        iconColorSuccess: '#28A745',                // 成功消息图标颜色：绿色
        colorInfo: 'rgba(23, 162, 184, 0.1)',       // 信息消息背景色：浅蓝色半透明
        borderInfo: '1px solid rgba(23, 162, 184, 0.3)', // 信息消息边框：蓝色边框
        textColorInfo: '#17a2b8',                   // 信息消息文字颜色：蓝色
        iconColorInfo: '#17a2b8',                   // 信息消息图标颜色：蓝色
        colorWarning: 'rgba(255, 193, 7, 0.1)',     // 警告消息背景色：浅黄色半透明
        borderWarning: '1px solid rgba(255, 193, 7, 0.3)', // 警告消息边框：黄色边框
        textColorWarning: '#FFC107',                // 警告消息文字颜色：黄色
        iconColorWarning: '#FFC107',                // 警告消息图标颜色：黄色
        colorError: 'rgba(220, 53, 69, 0.1)',       // 错误消息背景色：浅红色半透明
        borderError: '1px solid rgba(220, 53, 69, 0.3)', // 错误消息边框：红色边框
        textColorError: '#DC3545',                  // 错误消息文字颜色：红色
        iconColorError: '#DC3545'                   // 错误消息图标颜色：红色
    }
}

/**
 * 获取当前主题配置
 * @param isDark 是否为深色主题
 * @returns 对应的主题配置
 */
export function getThemeOverrides(isDark: boolean): GlobalThemeOverrides {
    return isDark ? darkThemeOverrides : lightThemeOverrides
}

/**
 * 主题配置类型导出
 */
export type {GlobalThemeOverrides}