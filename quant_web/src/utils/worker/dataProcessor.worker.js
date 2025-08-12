// 数据处理Worker - 负责数据清洗、转换和存储
import {Version as Papa} from "sass";

importScripts('https://cdnjs.cloudflare.com/ajax/libs/papaparse/5.3.2/papaparse.min.js');

// 监听主线程消息
self.addEventListener('message', async (e) => {
  const { task, payload } = e.data;

  try {
    switch (task) {
      case 'PROCESS_CSV':
        const processed = processCSV(payload);
        self.postMessage({
          task: 'CSV_PROCESSED',
          payload: processed
        });
        break;

      case 'VALIDATE_STOCK_DATA':
        const validationResult = validateStockData(payload);
        self.postMessage({
          task: 'DATA_VALIDATED',
          payload: validationResult
        });
        break;

      case 'SYNC_TO_DB':
        const syncResult = await syncDataToDB(payload);
        self.postMessage({
          task: 'DB_SYNC_COMPLETE',
          payload: syncResult
        });
        break;

      case 'GENERATE_FINANCIAL_INDICATORS':
        const indicators = generateFinancialIndicators(payload);
        self.postMessage({
          task: 'INDICATORS_GENERATED',
          payload: indicators
        });
        break;

      default:
        throw new Error(`Unknown task: ${task}`);
    }
  } catch (error) {
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
function processCSV({ data, config }) {
  return new Promise((resolve) => {
    Papa.parse(data, {
      ...config,
      complete: (results) => {
        resolve({
          meta: results.meta,
          data: cleanData(results.data)
        });
      }
    });
  });
}

// 数据清洗逻辑
function cleanData(rows) {
  return rows.map(row => {
    // 统一日期格式 (YYYY-MM-DD)
    if (row.trade_date) {
      row.trade_date = formatDate(row.trade_date);
    }

    // 转换数字类型
    const numericFields = [
      'open', 'high', 'low', 'close', 'pre_close', 'change',
      'pct_chg', 'vol', 'amount', 'turnover_rate'
    ];

    numericFields.forEach(field => {
      if (row[field]) {
        row[field] = parseFloat(row[field]);
      }
    });

    // 处理空值
    if (row.industry === '') row.industry = '未知';

    return row;
  });
}

// 日期格式化
function formatDate(dateStr) {
  // 支持多种日期格式转换
  if (/^\d{8}$/.test(dateStr)) {
    return `${dateStr.substr(0,4)}-${dateStr.substr(4,2)}-${dateStr.substr(6,2)}`;
  }
  return dateStr; // 其他格式直接返回
}

// 数据验证函数
function validateStockData(data) {
  const errors = [];
  const warnings = [];

  data.forEach((item, index) => {
    // 检查必填字段
    const requiredFields = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close'];
    requiredFields.forEach(field => {
      if (!item[field]) {
        errors.push(`行 ${index+1}: 缺少必填字段 [${field}]`);
      }
    });

    // 检查价格逻辑
    if (item.high < item.low) {
      errors.push(`行 ${index+1}: 最高价低于最低价`);
    }

    if (item.high < item.open || item.high < item.close) {
      warnings.push(`行 ${index+1}: 最高价小于开盘价或收盘价`);
    }

    // 检查涨跌幅计算
    if (item.pre_close && item.pct_chg) {
      const expectedChange = ((item.close - item.pre_close) / item.pre_close) * 100;
      if (Math.abs(expectedChange - item.pct_chg) > 0.01) {
        warnings.push(`行 ${index+1}: 涨跌幅计算不一致 (计算值: ${expectedChange.toFixed(4)}, 记录值: ${item.pct_chg})`);
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
function generateFinancialIndicators(data) {
  return data.map(item => {
    // 计算技术指标
    const indicators = {};

    // 示例指标计算
    if (item.vol && item.amount) {
      indicators.vwap = item.amount / (item.vol * 100); // 成交量加权平均价
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
async function syncDataToDB({ table, data }) {
  // 在实际应用中，这里会连接IndexedDB或发送到后端API
  const BATCH_SIZE = 1000;
  const total = data.length;
  let processed = 0;

  // 模拟分批处理
  for (let i = 0; i < total; i += BATCH_SIZE) {
    const batch = data.slice(i, i + BATCH_SIZE);

    // 模拟处理延迟
    await new Promise(resolve => setTimeout(resolve, 50));

    processed += batch.length;
    const progress = Math.round((processed / total) * 100);

    // 发送进度更新
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