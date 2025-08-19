import importlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import pandas as pd
import yaml

logger = logging.getLogger('data_source_manager')


class DataSourceManager:
    """统一管理多个数据源，支持优先级和混合获取策略，包含数据获取和处理功能"""

    def __init__(self, config_path: str = "config/data_sources.yaml", db_connector=None):
        self.fetch_strategy = 'hybrid'
        self.sources = []
        self.db_connector = db_connector  # 从外部传入的数据库连接器
        self.load_config(config_path)
        self._validate_sources()

    def _validate_sources(self):
        """验证数据源是否可用"""
        valid_sources = []
        for source in self.sources:
            instance = source['instance']
            # 特殊处理本地数据库源（总是可用）
            if source['type'] == 'db':
                valid_sources.append(source)
            elif not hasattr(instance, 'is_available') or instance.is_available():
                valid_sources.append(source)
            else:
                logger.warning(f"数据源 {source['name']} 不可用，将被忽略")

        self.sources = valid_sources
        logger.info(f"验证后可用数据源数量: {len(self.sources)}")

    def load_config(self, config_path: str):
        """加载数据源配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            self.fetch_strategy = config.get('data_fetch_strategy', 'hybrid')

            # 按优先级排序并初始化数据源
            sources = []
            for name, cfg in config['data_sources'].items():
                if not cfg.get('enabled', True):
                    continue

                source_type = cfg['type']
                # 特殊处理本地数据库源（使用传入的连接器）
                if source_type == 'db':
                    if not self.db_connector:
                        logger.warning("数据库连接器未提供，跳过本地数据库源")
                        continue

                    sources.append({
                        'name': name,
                        'type': source_type,
                        'priority': cfg.get('priority', 0),
                        'instance': self.db_connector  # 使用传入的连接器
                    })
                    continue

                try:
                    # 动态加载外部数据源模块
                    module_name = f"quantCore.database.data_sources.{source_type}_source"
                    module = importlib.import_module(module_name)
                    source_class = getattr(module, f"{source_type.capitalize()}Source")
                    source = source_class(cfg)
                    sources.append({
                        'name': name,
                        'type': source_type,
                        'priority': cfg.get('priority', 0),
                        'instance': source
                    })
                except Exception as e:
                    logger.error(f"初始化数据源失败 [{name}]: {str(e)}", exc_info=True)

            # 按优先级降序排列
            self.sources = sorted(sources, key=lambda x: x['priority'], reverse=True)
            logger.info(f"已加载 {len(self.sources)} 个数据源")
        except Exception as e:
            logger.error(f"加载数据源配置失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"配置加载失败: {str(e)}") from e

    def _try_offline_fetch(self, fetch_func: Callable, *args, **kwargs) -> Any:
        """尝试离线获取数据"""
        try:
            if self.fetch_strategy in ['hybrid', 'offline']:
                result = fetch_func(*args, **kwargs)
                if result is not None and (not isinstance(result, pd.DataFrame) or not result.empty):
                    return result
        except Exception as e:
            logger.warning(f"离线获取失败: {str(e)}")
        return None

    def _try_online_fetch(self, fetch_func: Callable, save_func: Optional[Callable] = None,
                          save_args: tuple = (), *args, **kwargs) -> Any:
        """尝试在线获取数据（跳过本地数据库源）"""
        if self.fetch_strategy not in ['hybrid', 'online']:
            return None

        for source in self.sources:
            # 跳过本地数据库源
            if source['type'] == 'postgres':
                continue

            try:
                result = fetch_func(source['instance'], *args, **kwargs)
                if result is not None and (not isinstance(result, pd.DataFrame) or not result.empty):
                    # 保存到本地数据库
                    if save_func and save_args:
                        try:
                            save_func(*save_args, result)
                        except Exception as e:
                            logger.error(f"保存数据失败: {str(e)}", exc_info=True)
                    return result
            except Exception as e:
                logger.warning(f"从数据源 {source['name']} 获取数据失败: {str(e)}")
        return None

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票历史数据
        根据配置策略选择数据获取方式
        """
        # 1. 尝试从本地数据库获取
        df = self._try_offline_fetch(
            self.db_connector.get_historical_data,
            symbol, start_date, end_date
        )

        if df is not None:
            df['data_source'] = 'local_db'  # 标记数据来源
            return df

        # 2. 尝试在线获取
        df = self._try_online_fetch(
            lambda instance, sym, s, e: instance.get_stock_history(sym, s, e),
            self._save_to_database, (symbol,),
            symbol, start_date, end_date
        )

        if df is not None:
            df['data_source'] = 'online_source'  # 标记数据来源
            return df

        # 3. 所有尝试都失败
        raise Exception(f"无法获取股票 {symbol} 的历史数据 ({start_date} 至 {end_date})")

    def get_daily_data(self, symbol: str, start: str, end: str,
                       adj: str = 'qfq') -> pd.DataFrame:
        """获取日线数据（自动处理复权）"""
        try:
            # 从数据源管理器获取原始数据
            df = self.get_stock_history(symbol, start, end)

            # 应用复权逻辑
            if adj == 'qfq':
                return self._apply_qfq_adjustment(df, symbol)
            elif adj == 'hfq':
                return self._apply_hfq_adjustment(df, symbol)
            return df
        except Exception as e:
            logger.error(f"获取日线数据失败 [{symbol}]: {str(e)}", exc_info=True)
            # 返回空DataFrame避免崩溃
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'turnover'])

    def _apply_qfq_adjustment(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """应用前复权计算"""
        try:
            # 获取复权因子
            factor_df = self.get_adjust_factor(symbol)

            if factor_df.empty:
                logger.warning(f"未找到 {symbol} 的复权因子，返回原始数据")
                return df

            # 合并因子数据
            merged = df.join(factor_df, how='left')

            # 前向填充缺失的因子值
            merged['factor'].ffill(inplace=True)

            # 计算复权价格
            last_factor = merged['factor'].iloc[-1] if not merged.empty else 1.0
            for col in ['open', 'high', 'low', 'close']:
                merged[col] = merged[col] * merged['factor'] / last_factor

            return merged[['open', 'high', 'low', 'close', 'volume', 'turnover']]
        except Exception as e:
            logger.error(f"前复权计算失败 [{symbol}]: {str(e)}", exc_info=True)
            return df

    def _apply_hfq_adjustment(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """应用后复权计算"""
        try:
            # 获取复权因子
            factor_df = self.get_adjust_factor(symbol)

            if factor_df.empty:
                logger.warning(f"未找到 {symbol} 的复权因子，返回原始数据")
                return df

            # 合并因子数据
            merged = df.join(factor_df, how='left')

            # 前向填充缺失的因子值
            merged['factor'].ffill(inplace=True)

            # 计算复权价格
            first_factor = merged['factor'].iloc[0] if not merged.empty else 1.0
            for col in ['open', 'high', 'low', 'close']:
                merged[col] = merged[col] * merged['factor'] / first_factor

            return merged[['open', 'high', 'low', 'close', 'volume', 'turnover']]
        except Exception as e:
            logger.error(f"后复权计算失败 [{symbol}]: {str(e)}", exc_info=True)
            return df

    def get_index_constituents(self, index_code: str) -> List[str]:
        """获取指数成分股"""
        # 1. 尝试从本地数据库获取
        result = self._try_offline_fetch(
            self.db_connector.get_index_constituents,
            index_code
        )
        if result is not None:
            return result

        # 2. 尝试在线获取
        result = self._try_online_fetch(
            lambda instance, code: instance.get_index_constituents(code),
            self.db_connector.save_index_constituents, (index_code,),
            index_code
        )

        if result is not None:
            return result

        raise Exception(f"无法获取指数 {index_code} 的成分股")

    def get_minute_data(self, symbol: str, date: str, freq: str) -> pd.DataFrame:
        """获取分钟线数据"""
        # 1. 尝试从本地数据库获取
        df = self._try_offline_fetch(
            self.db_connector.get_minute_data,
            symbol, date, freq
        )

        if df is not None:
            df['data_source'] = 'local_db'
            return df

        # 2. 尝试在线获取
        df = self._try_online_fetch(
            lambda instance, sym, d, f: instance.get_minute_data(sym, d, f),
            self._save_minute_data_to_database, (symbol, freq),
            symbol, date, freq
        )

        if df is not None:
            df['data_source'] = 'online_source'
            return df

        raise Exception(f"无法获取 {symbol} 在 {date} 的 {freq}分钟线数据")

    def _save_to_database(self, symbol: str, data: pd.DataFrame):
        """保存日线数据到本地数据库"""
        try:
            bars = []
            for index, row in data.iterrows():
                bars.append({
                    'symbol': symbol,
                    'date': index,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'],
                    'turnover': row.get('turnover', 0)
                })

            # 批量保存
            self.db_connector.batch_save_bars(bars)
            logger.info(f"已将 {symbol} 的 {len(bars)} 条日线数据保存到数据库")
        except Exception as e:
            logger.error(f"保存日线数据到数据库失败: {str(e)}", exc_info=True)

    def _save_minute_data_to_database(self, symbol: str, freq: str, data: pd.DataFrame):
        """保存分钟线数据到本地数据库"""
        try:
            minutes = []
            for index, row in data.iterrows():
                minutes.append({
                    'symbol': symbol,
                    'datetime': index,
                    'freq': freq,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'],
                    'turnover': row.get('turnover', 0)
                })

            # 批量保存
            self.db_connector.batch_save_minute_bars(minutes)
            logger.info(f"已将 {symbol} 的 {len(minutes)} 条{freq}分钟线数据保存到数据库")
        except Exception as e:
            logger.error(f"保存分钟线数据到数据库失败: {str(e)}", exc_info=True)

    def get_adjust_factor(self, symbol: str) -> pd.DataFrame:
        """获取复权因子"""
        # 1. 尝试从本地数据库获取
        df = self._try_offline_fetch(
            self.db_connector.get_adjust_factors,
            symbol
        )
        if df is not None:
            return df

        # 2. 尝试在线获取
        df = self._try_online_fetch(
            lambda instance, sym: instance.get_adjust_factor(sym),
            self.db_connector.save_adjust_factors, (symbol,),
            symbol
        )

        if df is not None:
            return df

        logger.warning(f"无法获取 {symbol} 的复权因子，返回空DataFrame")
        return pd.DataFrame()

    def get_latest_bar(self, symbol: str, interval: str = '1min') -> Optional[Dict[str, Any]]:
        """
        获取最新的K线数据

        参数:
            symbol: 股票代码
            interval: K线间隔，如 '1min', '5min', '15min'

        返回:
            包含最新K线数据的字典，格式:
            {
                'symbol': 股票代码,
                'datetime': 时间戳,
                'open': 开盘价,
                'high': 最高价,
                'low': 最低价,
                'close': 收盘价,
                'volume': 成交量,
                'turnover': 成交额（可选）
            }
        """
        try:
            # 获取当前时间
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')

            # 获取当天的分钟线数据
            df = self.get_minute_data(symbol, date_str, interval)

            if df.empty:
                return None

            # 获取最新的一行数据
            latest_row = df.iloc[-1]

            return {
                'symbol': symbol,
                'datetime': latest_row.name,  # 假设index是时间戳
                'open': latest_row['open'],
                'high': latest_row['high'],
                'low': latest_row['low'],
                'close': latest_row['close'],
                'volume': latest_row['volume'],
                'turnover': latest_row.get('turnover', 0)
            }
        except Exception as e:
            logger.error(f"获取最新K线数据失败 [{symbol}-{interval}]: {str(e)}", exc_info=True)
            return None

    def get_financial_data(self, symbol: str, period: str = 'latest') -> Dict[str, Any]:
        """获取财务数据

        Args:
            symbol: 股票代码
            period: 财报期间，格式 'YYYY Q1-Q4' 或 'latest' 表示最新财报

        Returns:
            Dict: 财务数据字典
        """
        # 1. 尝试从本地数据库获取
        if self.fetch_strategy in ['hybrid', 'offline']:
            try:
                data = self.db_connector.get_financial_data(symbol, period)
                if data:
                    return data
            except Exception as e:
                logger.warning(f"从本地数据库获取财务数据失败: {str(e)}")

        # 2. 尝试在线获取
        if self.fetch_strategy in ['hybrid', 'online']:
            for source in self.sources:
                if source['type'] != 'postgres' and hasattr(source['instance'], 'get_financial_data'):
                    try:
                        data = source['instance'].get_financial_data(symbol, period)
                        if data:
                            # 保存到数据库
                            self.db_connector.save_financial_data(symbol, period, data)
                            return data
                    except Exception as e:
                        logger.warning(f"从数据源 {source['name']} 获取财务数据失败: {str(e)}")

        logger.error(f"无法获取 {symbol} 的财务数据 (期间: {period})")
        return {}

    def get_ashare_list(self) -> List[Dict[str, str]]:
        """获取A股列表

        Returns:
            List[Dict]: 包含股票代码和名称的字典列表
            [{'symbol': '600000.SH', 'name': '浦发银行'}, ...]
        """
        # 1. 尝试从本地数据库获取
        if self.fetch_strategy in ['hybrid', 'offline']:
            try:
                stock_list = self.db_connector.get_ashare_list()
                if stock_list:
                    return stock_list
            except Exception as e:
                logger.warning(f"从本地数据库获取A股列表失败: {str(e)}")

        # 2. 尝试在线获取
        if self.fetch_strategy in ['hybrid', 'online']:
            for source in self.sources:
                if source['type'] != 'db' and hasattr(source['instance'], 'get_ashare_list'):
                    try:
                        stock_list = source['instance'].get_ashare_list()
                        if stock_list:
                            # 保存到数据库
                            self.db_connector.save_ashare_list(stock_list)
                            return stock_list
                    except Exception as e:
                        logger.warning(f"从数据源 {source['name']} 获取A股列表失败: {str(e)}")

        logger.error("无法获取A股列表")
        return []

    def get_financial_indicator(self, symbol: str, indicator: str,
                               start: str, end: str) -> pd.Series:
        """获取财务指标时间序列

        Args:
            symbol: 股票代码
            indicator: 指标名称，如 'roe', 'net_profit_margin'
            start: 开始期间 (YYYY-MM-DD)
            end: 结束期间 (YYYY-MM-DD)

        Returns:
            pd.Series: 指标时间序列，索引为日期
        """
        # 1. 尝试从本地数据库获取
        if self.fetch_strategy in ['hybrid', 'offline']:
            try:
                series = self.db_connector.get_financial_indicator(symbol, indicator, start, end)
                if not series.empty:
                    return series
            except Exception as e:
                logger.warning(f"从本地数据库获取财务指标失败: {str(e)}")

        # 2. 尝试在线获取
        if self.fetch_strategy in ['hybrid', 'online']:
            for source in self.sources:
                if source['type'] != 'postgres' and hasattr(source['instance'], 'get_financial_indicator'):
                    try:
                        series = source['instance'].get_financial_indicator(symbol, indicator, start, end)
                        if not series.empty:
                            # 保存到数据库
                            self.db_connector.save_financial_indicator(symbol, indicator, series)
                            return series
                    except Exception as e:
                        logger.warning(f"从数据源 {source['name']} 获取财务指标失败: {str(e)}")

        logger.error(f"无法获取 {symbol} 的财务指标 {indicator} (期间: {start} 至 {end})")
        return pd.Series()

    def set_primary_source(self, source_name: str):
        """设置首选数据源"""
        for i, source in enumerate(self.sources):
            if source['name'] == source_name:
                self.sources.insert(0, self.sources.pop(i))
                logger.info(f"已将 {source_name} 设为首选数据源")
                return
        logger.warning(f"未找到数据源: {source_name}")

    def set_fetch_strategy(self, strategy: str):
        """设置数据获取策略"""
        valid_strategies = ['hybrid', 'online', 'offline']
        if strategy in valid_strategies:
            self.fetch_strategy = strategy
            logger.info(f"数据获取策略已更新为: {strategy}")
        else:
            logger.error(f"无效的数据获取策略: {strategy}")
            raise ValueError(f"无效策略，必须是: {', '.join(valid_strategies)}")

    def switch_data_source(self, source_name: str):
        """切换首选数据源"""
        try:
            self.set_primary_source(source_name)
            logger.info(f"已切换到数据源: {source_name}")
        except Exception as e:
            logger.error(f"切换数据源失败: {str(e)}", exc_info=True)