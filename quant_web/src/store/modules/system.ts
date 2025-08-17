import {Module} from 'vuex';
import api from '../../api/system';
import {RootState} from '../types';

interface SystemState {
    connections: {
        dataSource: boolean;
        tradeGateway: boolean;
        strategyEngine: boolean;
    };
    resourceUsage: {
        cpu: number;
        memory: number;
        disk: number;
        network: number;
    };
    logs: any[];
    tasks: any[];
    config: any;
    services: Record<string, string>;
    database: {
        size: number;
        tables: number;
        lastBackup: string;
    };
}

const systemModule: Module<SystemState, RootState> = {
    namespaced: true,
    state: {
        connections: {
            dataSource: false,
            tradeGateway: false,
            strategyEngine: false
        },
        resourceUsage: {
            cpu: 0,
            memory: 0,
            disk: 0,
            network: 0
        },
        logs: [],
        tasks: [],
        config: {},
        services: {},
        database: {
            size: 0,
            tables: 0,
            lastBackup: ''
        }
    },
    mutations: {
        SET_CONNECTIONS(state, connections) {
            state.connections = connections;
        },
        SET_RESOURCE_USAGE(state, usage) {
            state.resourceUsage = usage;
        },
        SET_LOGS(state, logs) {
            state.logs = logs;
        },
        SET_TASKS(state, tasks) {
            state.tasks = tasks;
        },
        SET_CONFIG(state, config) {
            state.config = config;
        },
        SET_SERVICES(state, services) {
            state.services = services;
        },
        SET_DATABASE(state, database) {
            state.database = database;
        }
    },
    actions: {
        // 确保 action 名称完全匹配
        async loadInitialData({commit}) {
            return new Promise((resolve, reject) => {
                // 你的初始化逻辑
                api.loadData().then(data => {
                    commit('SET_DATA', data)
                    resolve()
                }).catch(reject)
            })
        },
        async checkConnections({commit}) {
            try {
                const status = await api.checkConnections();
                commit('SET_CONNECTIONS', status);
                return status;
            } catch (error) {
                console.error('检查连接状态失败:', error);
                throw error;
            }
        },
        async getResourceUsage({commit}) {
            try {
                const usage = await api.getResourceUsage();
                commit('SET_RESOURCE_USAGE', usage);
                return usage;
            } catch (error) {
                console.error('获取资源使用情况失败:', error);
                throw error;
            }
        },
        async getSystemLogs({commit}, params) {
            try {
                const logs = await api.getSystemLogs(params);
                commit('SET_LOGS', logs.logs);
                return logs;
            } catch (error) {
                console.error('获取系统日志失败:', error);
                throw error;
            }
        },
        async syncDataSource(_, source: string) {
            try {
                return await api.syncDataSource(source);
            } catch (error) {
                console.error('同步数据源失败:', error);
                throw error;
            }
        },
        async getTaskQueueStatus({commit}) {
            try {
                const tasks = await api.getTaskQueueStatus();
                commit('SET_TASKS', tasks);
                return tasks;
            } catch (error) {
                console.error('获取任务队列状态失败:', error);
                throw error;
            }
        },
        async getSystemConfig({commit}) {
            try {
                const config = await api.getSystemConfig();
                commit('SET_CONFIG', config);
                return config;
            } catch (error) {
                console.error('获取系统配置失败:', error);
                throw error;
            }
        },
        async updateSystemConfig({commit}, config) {
            try {
                const updatedConfig = await api.updateSystemConfig(config);
                commit('SET_CONFIG', updatedConfig);
                return updatedConfig;
            } catch (error) {
                console.error('更新系统配置失败:', error);
                throw error;
            }
        },
        async getServiceStatus({commit, state}, serviceName: string) { // 新增state参数
            try {
                const status = await api.getServiceStatus(serviceName);
                commit('SET_SERVICES', {
                    ...state.services,
                    [serviceName]: status
                });
                return status;
            } catch (error) {
                console.error('获取服务状态失败:', error);
                throw error;
            }
        },
        async restartService(_, serviceName: string) {
            try {
                return await api.restartService(serviceName);
            } catch (error) {
                console.error('重启服务失败:', error);
                throw error;
            }
        },
        async getDatabaseStatus({commit}) {
            try {
                const database = await api.getDatabaseStatus();
                commit('SET_DATABASE', database);
                return database;
            } catch (error) {
                console.error('获取数据库状态失败:', error);
                throw error;
            }
        },
        async createDatabaseBackup() {
            try {
                return await api.createDatabaseBackup();
            } catch (error) {
                console.error('创建数据库备份失败:', error);
                throw error;
            }
        }
    }
};

export default systemModule;