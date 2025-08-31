import request from '@/utils/request'
import {handleResponse} from '@/utils/responseHandler'

interface ConnectionStatus {
    dataSource: boolean;
    tradeGateway: boolean;
    strategyEngine: boolean;
}

interface ResourceUsage {
    cpu: number;
    memory: number;
    disk: number;
    network: number;
}

interface LogResult {
    logs: any[];
    total: number;
    page: number;
}

interface DatabaseStatus {
    size: number;
    tables: number;
    lastBackup: string;
}

export default {
    async checkConnections(): Promise<ConnectionStatus> {
        return request.get('/system/connections')
            .then(handleResponse)
            .then((data: any) => ({
                dataSource: data.dataSource,
                tradeGateway: data.tradeGateway,
                strategyEngine: data.strategyEngine
            }))
    },

    async getResourceUsage(): Promise<ResourceUsage> {
        return request.get('/system/resources')
            .then(handleResponse)
            .then((data: any) => ({
                cpu: data.cpu,
                memory: data.memory,
                disk: data.disk,
                network: data.network
            }))
    },

    async getSystemLogs(params: any): Promise<LogResult> {
        return request.get('/system/logs', {params})
            .then(handleResponse)
            .then((data: { logs: any[], total: number, page: number }) => ({
                logs: data.logs,
                total: data.total,
                page: data.page
            }))
    },

    async syncDataSource(source: string): Promise<{ success: boolean; message: string; syncId: string }> {
        return request.post(`/system/sync/${source}`)
            .then(handleResponse)
            .then((data: any) => ({
                success: data.success,
                message: data.message,
                syncId: data.syncId
            }))
    },

    async getTaskQueueStatus(): Promise<any[]> {
        return request.get('/system/tasks')
            .then(handleResponse)
            .then((data: { tasks: any[] }) => data.tasks) // 添加类型注解
    },

    async getSystemConfig(): Promise<any> {
        return request.get('/system/config')
            .then(handleResponse)
            .then((data: { config: any }) => data.config) // 添加类型注解
    },

    async updateSystemConfig(config: any): Promise<any> {
        return request.put('/system/config', config)
            .then(handleResponse)
            .then((data: { updatedConfig: any }) => data.updatedConfig) // 添加类型注解
    },

    async getServiceStatus(serviceName: string): Promise<string> {
        return request.get(`/system/services/${serviceName}/status`)
            .then(handleResponse)
            .then((data: { status: string }) => data.status) // 添加类型注解
    },

    async restartService(serviceName: string): Promise<{ success: boolean; message: string }> {
        return request.post(`/system/services/${serviceName}/restart`)
            .then(handleResponse)
            .then((data: any) => ({
                success: data.success,
                message: data.message
            }))
    },

    async getDatabaseStatus(): Promise<DatabaseStatus> {
        return request.get('/system/database')
            .then(handleResponse)
            .then((data: any) => ({
                size: data.size,
                tables: data.tables,
                lastBackup: data.lastBackup
            }))
    },

    async createDatabaseBackup(): Promise<{ success: boolean; backupId: string }> {
        return request.post('/system/database/backup')
            .then(handleResponse)
            .then((data: any) => ({
                success: data.success,
                backupId: data.backupId
            }))
    },

       /**
     * 加载系统初始数据（聚合连接状态、资源使用、数据库状态）
     * @returns 聚合后的初始数据
     */
   async loadInitialData(): Promise<{
        connections: ConnectionStatus;
        resourceUsage: ResourceUsage;
        databaseStatus: DatabaseStatus;
    }> {
        try {
            // 并行请求多个初始数据接口，提升加载效率
            const [connections, resourceUsage, databaseStatus] = await Promise.all([
                this.checkConnections(),    // 连接状态
                this.getResourceUsage(),    // 资源使用
                this.getDatabaseStatus()    // 数据库状态
            ]);
            return { connections, resourceUsage, databaseStatus };
        } catch (error) {
            console.error('系统初始数据加载失败:', error);
            // 返回默认值而不是抛出错误，避免阻塞应用启动
            return {
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
                databaseStatus: {
                    size: 0,
                    tables: 0,
                    lastBackup: ''
                }
            };
        }
    }
}