import request from '@/utils/request'
import {handleResponse} from '@/utils/responseHandler'

export interface User {
    id: string;
    name: string;
    email: string;
    // ...其他用户信息
}

export interface LoginResponse {
    token: string;
    user: User;
    expiresIn: number;
}

export interface ActivityLog {
    id: string;
    action: string;
    timestamp: string;
    // ...其他日志信息
}

export interface ActivityLogResult {
    logs: ActivityLog[];
    total: number;
    page: number;
}

export default {
    async login(credentials: { username: string; password: string }): Promise<LoginResponse> {
        return request.post('/auth/login', credentials)
            .then(handleResponse)
            .then((data: any) => ({
                token: data.token,
                user: data.user,
                expiresIn: data.expiresIn
            }))
    },

    logout() {
        return request.post('/auth/logout')
            .then(handleResponse)
    },

    async getUserInfo(): Promise<User> {
        return request.get('/user/info')
            .then(handleResponse)
            .then((data: { user: User }) => data.user) // 添加类型注解
    },

    async updateUserInfo(userInfo: Partial<User>): Promise<User> {
        return request.put('/user/info', userInfo)
            .then(handleResponse)
            .then((data: { updatedUser: User }) => data.updatedUser) // 添加类型注解
    },

    async changePassword(oldPassword: string, newPassword: string): Promise<{ success: boolean; message: string }> {
        return request.post('/user/password', {oldPassword, newPassword})
            .then(handleResponse)
            .then((data: any) => ({
                success: data.success,
                message: data.message
            }))
    },

    async getUserPreferences(): Promise<any> {
        return request.get('/user/preferences')
            .then(handleResponse)
            .then((data: { preferences: any }) => data.preferences) // 添加类型注解
    },

    async updateUserPreferences(preferences: any): Promise<any> {
        return request.put('/user/preferences', preferences)
            .then(handleResponse)
            .then((data: { updatedPreferences: any }) => data.updatedPreferences) // 添加类型注解
    },

    async getNotificationSettings(): Promise<any> {
        return request.get('/user/notifications')
            .then(handleResponse)
            .then((data: { notifications: any }) => data.notifications) // 添加类型注解
    },

    async updateNotificationSettings(settings: any): Promise<any> {
        return request.put('/user/notifications', settings)
            .then(handleResponse)
            .then((data: { updatedSettings: any }) => data.updatedSettings) // 添加类型注解
    },

    async getApiKeys(): Promise<any[]> {
        return request.get('/user/api-keys')
            .then(handleResponse)
            .then((data: { keys: any[] }) => data.keys) // 添加类型注解
    },

    async createApiKey(name: string): Promise<any> {
        return request.post('/user/api-keys', {name})
            .then(handleResponse)
            .then((data: { newKey: any }) => data.newKey) // 添加类型注解
    },

    async deleteApiKey(keyId: string) {
        return request.delete(`/user/api-keys/${keyId}`)
            .then(handleResponse)
    },

    async getUserActivityLogs(page: number = 1, pageSize: number = 20): Promise<ActivityLogResult> {
        return request.get('/user/activity', {
            params: {page, pageSize}
        })
            .then(handleResponse)
            .then((data: { logs: ActivityLog[], total: number, page: number }) => ({
                logs: data.logs,
                total: data.total,
                page: data.page
            }))
    },

    async enableTwoFactorAuth(): Promise<{ secret: string; qrCode: string }> {
        return request.post('/user/two-factor/enable')
            .then(handleResponse)
            .then((data: any) => ({
                secret: data.secret,
                qrCode: data.qrCode
            }))
    },

    async verifyTwoFactorAuth(token: string): Promise<{ success: boolean; recoveryCodes: string[] }> {
        return request.post('/user/two-factor/verify', {token})
            .then(handleResponse)
            .then((data: any) => ({
                success: data.success,
                recoveryCodes: data.recoveryCodes
            }))
    },

    // 禁用双因素认证
    disableTwoFactorAuth() {
        return request.post('/user/two-factor/disable')
            .then(handleResponse)
    }
}