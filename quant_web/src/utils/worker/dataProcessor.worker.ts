// dataProcessor.worker.ts
// 声明PapaParse类型
declare const Papa: any;

// 定义类型
type CSVProcessingConfig = {
  header?: boolean;
  dynamicTyping?: boolean;
  skipEmptyLines?: boolean | 'greedy';
  [key: string]: any;
};

type ValidationResult = {
  valid: boolean;
  errorCount: number;
  warningCount: number;
  errors: string[];
  warnings: string[];
};

type StockData = {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  pre_close?: number;
  pct_chg?: number;
  vol?: number;
  amount?: number;
  turnover_rate?: number;
  industry?: string;
  [key: string]: any;
};

type SyncProgress = {
  table: string;
  processed: number;
  total: number;
  progress: number;
};

// 监听主线程消息
self.addEventListener('message', async (e: MessageEvent<{ task: string; payload: any }>) => {
  const { task, payload } = e.data;

  try {
    switch (task) {
      case 'PROCESS_CSV': {
        const processed = await processCSV(payload);
        self.postMessage({
          task: 'CSV_PROCESSED',
          payload: processed
        });
        break;
      }
      case 'VALIDATE_STOCK_DATA': {
        const validationResult = validateStockData(payload);
        self.postMessage({
          task: 'DATA_VALIDATED',
          payload: validationResult
        });
        break;
      }
      case 'SYNC_TO_DB': {
        const syncResult = await syncDataToDB(payload);
        self.postMessage({
          task: 'DB_SYNC_COMPLETE',
          payload: syncResult
        });
        break;
      }
      case 'GENERATE_FINANCIAL_INDICATORS': {
        const indicators = generateFinancialIndicators(payload);
        self.postMessage({
          task: 'INDICATORS_GENERATED',
          payload: indicators
        });
        break;
      }
      default:
        throw new Error(`Unknown task: ${task}`);
    }
  } catch (error: any) {
    self.postMessage({
      task: 'ERROR',
      payload: {
        originalTask: task,
        error: error.message,
        stack: error.stack
      }
    });
  }
});

// CSV处理函数
async function processCSV({ data, config }: { data: string; config: CSVProcessingConfig }): Promise<{ meta: any; data: StockData[] }> {
  return new Promise((resolve) => {
    Papa.parse(data, {
      ...config,
      complete: (results: any) => {
        resolve({
          meta: results.meta,
          data: cleanData(results.data)
        });
      }
    });
  });
}

// 数据清洗逻辑
function cleanData(rows: any[]): StockData[] {
  return rows.map((row: any) => {
    const cleanRow: any = { ...row };

    // 统一日期格式
    if (cleanRow.trade_date) {
      cleanRow.trade_date = formatDate(cleanRow.trade_date);
    }

    // 转换数字类型
    const numericFields = [
      'open', 'high', 'low', 'close', 'pre_close', 'change',
      'pct_chg', 'vol', 'amount', 'turnover_rate'
    ];

    numericFields.forEach(field => {
      if (cleanRow[field] !== undefined && cleanRow[field] !== null && cleanRow[field] !== '') {
        cleanRow[field] = parseFloat(cleanRow[field]);
      }
    });

    // 处理空值
    if (cleanRow.industry === '') cleanRow.industry = '未知';

    return cleanRow as StockData;
  });
}

// 日期格式化
function formatDate(dateStr: string): string {
  if (/^\d{8}$/.test(dateStr)) {
    return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
  }
  return dateStr;
}

// 数据验证函数
function validateStockData(data: StockData[]): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  data.forEach((item, index) => {
    // 检查必填字段
    const requiredFields = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close'];
    requiredFields.forEach(field => {
      if (item[field] === undefined || item[field] === null || item[field] === '') {
        errors.push(`行 ${index + 1}: 缺少必填字段 [${field}]`);
      }
    });

    // 检查价格逻辑
    if (item.high < item.low) {
      errors.push(`行 ${index + 1}: 最高价低于最低价`);
    }

    if (item.high < item.open || item.high < item.close) {
      warnings.push(`行 ${index + 1}: 最高价小于开盘价或收盘价`);
    }

    // 检查涨跌幅计算
    if (item.pre_close !== undefined && item.pct_chg !== undefined) {
      const expectedChange = ((item.close - item.pre_close) / item.pre_close) * 100;
      if (Math.abs(expectedChange - item.pct_chg) > 0.01) {
        warnings.push(`行 ${index + 1}: 涨跌幅计算不一致 (计算值: ${expectedChange.toFixed(4)}, 记录值: ${item.pct_chg})`);
      }
    }
  });

  return {
    valid: errors.length === 0,
    errorCount: errors.length,
    warningCount: warnings.length,
    errors,
    warnings
  };
}

// 生成财务指标
function generateFinancialIndicators(data: StockData[]): StockData[] {
  return data.map(item => {
    const indicators: Record<string, number> = {};

    // 计算技术指标
    if (item.vol && item.amount) {
      indicators.vwap = item.amount / (item.vol * 100);
    }

    if (item.close && item.open) {
      indicators.range_pct = ((item.high - item.low) / item.open) * 100;
    }

    return {
      ...item,
      indicators
    };
  });
}

// 模拟数据库同步
async function syncDataToDB({ table, data }: { table: string; data: any[] }): Promise<{
  success: boolean;
  table: string;
  insertedCount: number;
  timestamp: string;
}> {
  const BATCH_SIZE = 1000;
  const total = data.length;
  let processed = 0;

  for (let i = 0; i < total; i += BATCH_SIZE) {
    const batch = data.slice(i, i + BATCH_SIZE);
    await new Promise(resolve => setTimeout(resolve, 50));
    processed += batch.length;
    const progress = Math.round((processed / total) * 100);

    self.postMessage({
      task: 'DB_SYNC_PROGRESS',
      payload: {
        table,
        processed,
        total,
        progress
      }
    });
  }

  return {
    success: true,
    table,
    insertedCount: data.length,
    timestamp: new Date().toISOString()
  };
}