// 表单相关类型定义

/**
 * 表单字段验证规则接口
 */
export interface FormRule {
  required?: boolean;                      // 是否必填
  message?: string;                        // 验证失败提示信息
  pattern?: RegExp;                        // 正则表达式验证
  validator?: (value: any) => boolean;     // 自定义验证函数
  trigger?: 'change' | 'blur';             // 触发时机
  min?: number;                            // 最小值
  max?: number;                            // 最大值
  len?: number;                            // 长度限制
}

/**
 * 表单字段配置接口
 */
export interface FormField {
  name: string;                            // 字段名
  label: string;                           // 标签文本
  type: 'input' | 'select' | 'number' | 'date' | 'textarea' | 'checkbox' | 'radio'; // 字段类型
  placeholder?: string;                    // 占位符
  required?: boolean;                      // 是否必填
  disabled?: boolean;                      // 是否禁用
  rules?: FormRule[];                      // 验证规则
  options?: Array<{ label: string; value: any }>; // 选项（用于select/radio/checkbox）
  props?: Record<string, any>;             // 额外属性
}

/**
 * 表单配置接口
 */
export interface FormConfig {
  fields: FormField[];                     // 表单字段配置
  layout?: 'horizontal' | 'vertical';      // 布局方式
  labelWidth?: number | string;            // 标签宽度
  colon?: boolean;                         // 是否显示冒号
}

/**
 * 表单数据模型接口
 */
export type FormModel = Record<string, any>;

/**
 * 表单状态接口
 */
export interface FormState {
  model: FormModel;                        // 表单数据
  errors: Record<string, string>;          // 错误信息
  touched: Record<string, boolean>;        // 字段触摸状态
  submitting: boolean;                     // 提交中状态
  valid: boolean;                          // 表单是否有效
}

/**
 * 表单提交参数接口
 */
export interface FormSubmitParams<T = any> {
  data: T;                                 // 表单数据
  isValid: boolean;                        // 是否验证通过
  errors?: Record<string, string>;         // 错误信息
}

/**
 * 表单重置选项接口
 */
export interface FormResetOptions {
  clearErrors?: boolean;                   // 是否清除错误信息
  resetTouched?: boolean;                  // 是否重置触摸状态
  keepDefaultValues?: boolean;             // 是否保留默认值
}

/**
 * 动态表单字段接口（用于条件渲染）
 */
export interface DynamicFormField extends FormField {
  show?: (model: FormModel) => boolean;    // 显示条件函数
  disabled?: (model: FormModel) => boolean; // 禁用条件函数
}

/**
 * 表单步骤配置接口（用于多步骤表单）
 */
export interface FormStep {
  title: string;                           // 步骤标题
  description?: string;                    // 步骤描述
  fields: FormField[];                     // 步骤字段
  valid?: boolean;                         // 步骤是否有效
}