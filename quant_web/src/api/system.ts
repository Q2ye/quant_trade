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
    }
}