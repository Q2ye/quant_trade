// utils/converters/userConverter.ts
import { UserInfo } from '@/types/api/user';
import {User} from "@/types";

export class UserConverter {
  static fromApiResponse(apiUser: UserInfo): User {
    return {
      id: apiUser.id,
      username: apiUser.username,
      email: apiUser.email,
      phone: apiUser.phone || undefined,
      real_name: apiUser.realName || undefined,
      role: this.convertRole(apiUser.role), // 角色转换
      is_active: apiUser.isActive,
      last_login: apiUser.lastLogin || undefined,
      preferences: this.buildDefaultPreferences(), // 构建默认偏好设置
      created_at: apiUser.createdAt,
      updated_at: apiUser.updatedAt
    };
  }

  private static convertRole(apiRole: string): 'admin' | 'user' | 'guest' {
    switch (apiRole) {
      case 'admin': return 'admin';
      case 'user': return 'user';
      default: return 'guest';
    }
  }

  private static buildDefaultPreferences(): User['preferences'] {
    return {
      theme: 'auto',
      language: 'zh-CN',
      notifications: {
        email: true,
        push: true,
        sms: false
      },
      trading: {
        default_order_type: 'limit',
        default_volume: 100,
        confirm_before_trade: true
      },
      dashboard: {
        default_view: 'overview',
        refresh_interval: 30
      }
    };
  }
}