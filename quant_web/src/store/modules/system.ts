// quant_web/src/store/modules/system.ts
import {Module} from 'vuex';
import api from '@/api/system';
import {RootState} from '@/types';
import {DataSourceStatus, ScheduledTask, SystemLog, SystemSetting} from '@/types/entities/system';
import { ConnectionStatus, ResourceUsage, DatabaseStatus } from '@/api/system';

/**
 * 系统管理状态接口
 * 负责管理系统配置、监控数据、日志、任务等状态
 */
export interface SystemState {
    // 连接状态
    connections: {
        dataSource: boolean;      // 数据源连接状态
        tradeGateway: boolean;    // 交易网关连接状态
        strategyEngine: boolean;  // 策略引擎连接状态
        database: boolean;        // 数据库连接状态
        redis: boolean;           // Redis连接状态
    };

    // 资源使用情况
    resourceUsage: {
        cpu: number;              // CPU使用率
        memory: number;           // 内存使用率
        disk: number;             // 磁盘使用率
        network: number;          // 网络使用率
    };

    // 系统日志
    logs: SystemLog[];

    // 任务队列
    tasks: ScheduledTask[];

    // 系统配置
    config: SystemSetting[];

    // 服务状态
    services: Record<string, string>;

    // 数据库状态
    database: {
        size: number;             // 数据库大小
        tables: number;           // 表数量
        lastBackup: string;       // 最后备份时间
        connections: number;      // 连接数
    };

    // 数据源状态
    dataSources: DataSourceStatus[];

    // 加载状态
    loading: {
        initial: boolean;         // 初始数据加载
        logs: boolean;            // 日志加载
        config: boolean;          // 配置加载
        tasks: boolean;           // 任务加载
        metrics: boolean;         // 指标加载
    };

    // 错误信息
    error: string | null;

    // 数据加载标志
    dataLoaded: boolean;
}

const systemModule: Module<SystemState, RootState> = {
    namespaced: true,

    state: {
        connections: {
            dataSource: false,
            tradeGateway: false,
            strategyEngine: false,
            database: false,
            redis: false
        },
        resourceUsage: {
            cpu: 0,
            memory: 0,
            disk: 0,
            network: 0
        },
        logs: [],
        tasks: [],
        config: [],
        services: {},
        database: {
            size: 0,
            tables: 0,
            lastBackup: '',
            connections: 0
        },
        dataSources: [],
        loading: {
            initial: false,
            logs: false,
            config: false,
            tasks: false,
            metrics: false
        },
        error: null,
        dataLoaded: false
    },

    mutations: {
        /**
         * 设置连接状态
         */
        SET_CONNECTIONS(state, connections: SystemState['connections']) {
            state.connections = connections;
        },

        /**
         * 设置资源使用情况
         */
        SET_RESOURCE_USAGE(state, usage: SystemState['resourceUsage']) {
            state.resourceUsage = usage;
        },

        /**
         * 设置系统日志
         */
        SET_LOGS(state, logs: SystemLog[]) {
            state.logs = logs;
        },

        /**
         * 设置任务队列
         */
        SET_TASKS(state, tasks: ScheduledTask[]) {
            state.tasks = tasks;
        },

        /**
         * 设置系统配置
         */
        SET_CONFIG(state, config: SystemSetting[]) {
            state.config = config;
        },

        /**
         * 设置服务状态
         */
        SET_SERVICES(state, services: Record<string, string>) {
            state.services = services;
        },

        /**
         * 设置数据库状态
         */
        SET_DATABASE(state, database: SystemState['database']) {
            state.database = database;
        },

        /**
         * 设置数据源状态
         */
        SET_DATA_SOURCES(state, dataSources: DataSourceStatus[]) {
            state.dataSources = dataSources;
        },

        /**
         * 设置加载状态
         */
        SET_LOADING(state, payload: { key: keyof SystemState['loading']; value: boolean }) {
            state.loading[payload.key] = payload.value;
        },

        /**
         * 设置错误信息
         */
        SET_ERROR(state, error: string | null) {
            state.error = error;
        },

        /**
         * 设置数据加载标志
         */
        SET_DATA_LOADED(state, loaded: boolean) {
            state.dataLoaded = loaded;
        }
    },

    actions: {
        /**
         * 加载初始系统数据 - 修复版本
         */
        async loadInitialData({commit, state}) {
            if (state.dataLoaded) {
                return;
            }

            commit('SET_LOADING', {key: 'initial', value: true});
            commit('SET_ERROR', null);

            try {
                // 使用更安全的API调用方式，添加错误处理
                const requests = [
                    api.getConnections().catch(error => {
                        console.warn('获取连接状态失败:', error);
                        return {
                            database: false,
                            redis: false,
                            tushare: false,
                            broker: false,
                            last_check: ''
                        } as ConnectionStatus;
                    }),
                    api.getResources().catch(error => {
                        console.warn('获取资源使用情况失败:', error);
                        return {
                            cpu_percent: 0,
                            memory_percent: 0,
                            memory_used: 0,
                            memory_total: 0,
                            disk_usage: 0,
                            network_io: { bytes_sent: 0, bytes_recv: 0 }
                        } as ResourceUsage;
                    }),
                    api.getDatabaseStatus().catch(error => {
                        console.warn('获取数据库状态失败:', error);
                        return {
                            total_tables: 0,
                            total_records: 0,
                            stock_data_count: 0,
                            trade_data_count: 0,
                            last_optimized: ''
                        } as DatabaseStatus;
                    })
                ];

                const [connectionsResponse, resourceUsageResponse, databaseStatusResponse] = await Promise.all(requests);

                // 安全地提取数据，添加类型断言
                const connections = connectionsResponse as ConnectionStatus;
                const resourceUsage = resourceUsageResponse as ResourceUsage;
                const databaseStatus = databaseStatusResponse as DatabaseStatus;

                // 更新状态 - 使用正确的字段映射
                commit('SET_CONNECTIONS', {
                    dataSource: connections.tushare || false,
                    tradeGateway: connections.broker || false,
                    strategyEngine: true, // 默认设为true，因为API中没有这个字段
                    database: connections.database || false,
                    redis: connections.redis || false
                });

                commit('SET_RESOURCE_USAGE', {
                    cpu: resourceUsage.cpu_percent || 0,
                    memory: resourceUsage.memory_percent || 0,
                    disk: resourceUsage.disk_usage || 0,
                    network: 0 // API中没有网络使用率字段
                });

                commit('SET_DATABASE', {
                    size: 0, // API中没有数据库大小字段
                    tables: databaseStatus.total_tables || 0,
                    lastBackup: databaseStatus.last_optimized || '',
                    connections: 0 // API中没有连接数字段
                });

                commit('SET_DATA_LOADED', true);

                return {connections, resourceUsage, databaseStatus};
            } catch (error) {
                const errorMsg = error instanceof Error ? error.message : '加载初始数据失败';
                commit('SET_ERROR', errorMsg);
                console.error('加载初始数据错误:', error);

                // 设置安全的默认状态
                commit('SET_CONNECTIONS', {
                    dataSource: false,
                    tradeGateway: false,
                    strategyEngine: false,
                    database: false,
                    redis: false
                });

                commit('SET_RESOURCE_USAGE', {
                    cpu: 0,
                    memory: 0,
                    disk: 0,
                    network: 0
                });

                commit('SET_DATABASE', {
                    size: 0,
                    tables: 0,
                    lastBackup: '',
                    connections: 0
                });

                commit('SET_DATA_LOADED', true); // 即使失败也标记为已加载，避免重复尝试

                return {
                    connections: {},
                    resourceUsage: {},
                    databaseStatus: {}
                };
            } finally {
                commit('SET_LOADING', {key: 'initial', value: false});
            }
        },

        /**
         * 检查系统连接状态 - 修复版本
         */
        async checkConnections({commit}) {
            try {
                const status = await api.getConnections().catch(error => {
                    console.warn('检查连接状态失败:', error);
                    return {
                        database: false,
                        redis: false,
                        tushare: false,
                        broker: false,
                        last_check: ''
                    } as ConnectionStatus;
                });

                commit('SET_CONNECTIONS', {
                    dataSource: status.tushare || false,
                    tradeGateway: status.broker || false,
                    strategyEngine: true, // 默认设为true
                    database: status.database || false,
                    redis: status.redis || false
                });
                return status;
            } catch (error) {
                console.error('检查连接状态失败:', error);
                // 不抛出错误，避免阻塞其他操作
                return {};
            }
        },

        /**
         * 获取资源使用情况 - 修复版本
         */
        async getResourceUsage({commit}) {
            commit('SET_LOADING', {key: 'metrics', value: true});
            try {
                const usage = await api.getResources().catch(error => {
                    console.warn('获取资源使用情况失败:', error);
                    return {
                        cpu_percent: 0,
                        memory_percent: 0,
                        memory_used: 0,
                        memory_total: 0,
                        disk_usage: 0,
                        network_io: { bytes_sent: 0, bytes_recv: 0 }
                    } as ResourceUsage;
                });

                commit('SET_RESOURCE_USAGE', {
                    cpu: usage.cpu_percent || 0,
                    memory: usage.memory_percent || 0,
                    disk: usage.disk_usage || 0,
                    network: 0 // API中没有网络使用率字段
                });
                return usage;
            } catch (error) {
                console.error('获取资源使用情况失败:', error);
                return {};
            } finally {
                commit('SET_LOADING', {key: 'metrics', value: false});
            }
        },

        /**
         * 获取系统日志
         */
        async getSystemLogs({commit}, params) {
            commit('SET_LOADING', {key: 'logs', value: true});
            try {
                const logs = await api.getSystemLogs(params);
                commit('SET_LOGS', logs || []);
                return logs;
            } catch (error) {
                console.error('获取系统日志失败:', error);
                throw error;
            } finally {
                commit('SET_LOADING', {key: 'logs', value: false});
            }
        },

        /**
         * 同步数据源
         */
        async syncDataSource(_, source: string) {
            try {
                return await api.triggerDataSync({
                    data_type: source,
                    start_date: undefined,
                    end_date: undefined,
                    symbols: undefined
                });
            } catch (error) {
                console.error('同步数据源失败:', error);
                throw error;
            }
        },

        /**
         * 获取系统配置
         */
        async getSystemConfig({commit}) {
            commit('SET_LOADING', {key: 'config', value: true});
            try {
                const config = await api.getSystemSettings();
                // 将系统设置转换为SystemSetting格式
                const systemSettings: SystemSetting[] = Object.entries(config).map(([key, value]) => ({
                    id: key,
                    key,
                    value,
                    type: typeof value as any,
                    description: '',
                    category: 'system',
                    is_public: false,
                    editable: true,
                    created_at: '',
                    updated_at: ''
                }));
                commit('SET_CONFIG', systemSettings);
                return config;
            } catch (error) {
                console.error('获取系统配置失败:', error);
                throw error;
            } finally {
                commit('SET_LOADING', {key: 'config', value: false});
            }
        },

        /**
         * 更新系统配置
         */
        async updateSystemConfig({commit}, config) {
            try {
                const updatedConfig = await api.updateSystemSettings(config);
                commit('SET_CONFIG', updatedConfig);
                return updatedConfig;
            } catch (error) {
                console.error('更新系统配置失败:', error);
                throw error;
            }
        },

        /**
         * 重启系统服务
         */
        async restartService(_, serviceName: string) {
            try {
                return await api.restartService(serviceName);
            } catch (error) {
                console.error('重启服务失败:', error);
                throw error;
            }
        },

        /**
         * 获取数据库状态
         */
        async getDatabaseStatus({commit}) {
            try {
                const database = await api.getDatabaseStatus();
                commit('SET_DATABASE', {
                    size: 0, // API中没有数据库大小字段
                    tables: database.total_tables || 0,
                    lastBackup: database.last_optimized || '',
                    connections: 0 // API中没有连接数字段
                });
                return database;
            } catch (error) {
                console.error('获取数据库状态失败:', error);
                throw error;
            }
        }
    },

    getters: {
        /**
         * 检查是否正在加载
         */
        isLoading: state => state.loading.initial,

        /**
         * 检查是否有错误
         */
        hasError: state => state.error !== null,

        /**
         * 获取错误信息
         */
        errorMessage: state => state.error,

        /**
         * 检查数据是否已加载
         */
        isDataLoaded: state => state.dataLoaded,

        /**
         * 获取所有连接状态
         */
        connectionStatus: state => state.connections,

        /**
         * 检查所有连接是否正常
         */
        allConnectionsOk: state =>
            Object.values(state.connections).every(status => status === true),

        /**
         * 获取系统健康状态
         */
        systemHealth: state => ({
            connections: state.connections,
            resources: state.resourceUsage,
            database: state.database
        })
    }
};

export default systemModule;