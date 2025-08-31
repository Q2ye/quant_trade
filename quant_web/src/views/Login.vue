<template>
  <div class="login-container">
    <div class="login-form">
      <h2>量化交易平台</h2>
      <div class="form-group">
        <label for="username">用户名</label>
        <input
          type="text"
          id="username"
          v-model="username"
          placeholder="请输入用户名"
          :disabled="isLoading"
        />
      </div>
      <div class="form-group">
        <label for="password">密码</label>
        <input
          type="password"
          id="password"
          v-model="password"
          placeholder="请输入密码"
          :disabled="isLoading"
          @keyup.enter="handleLogin"
        />
      </div>
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>
      <button
        class="login-btn"
        :disabled="isLoading"
        @click="handleLogin"
      >
        {{ isLoading ? '登录中...' : '登录' }}
      </button>
      <div v-if="isTestMode" class="test-mode-notice">
        <p>测试模式已启用</p>
        <button @click="fillCredentials('admin', 'admin123')">
          填充管理员凭据
        </button>
        <button @click="fillCredentials('user', 'user123')">
          填充用户凭据
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from 'vuex';
import request from '@/utils/request';

export default {
  name: 'Login',
  setup() {
    const username = ref('');
    const password = ref('');
    const isLoading = ref(false);
    const errorMessage = ref('');
    const isTestMode = ref(false);
    const router = useRouter();
    const store = useStore();

    // 检查是否测试模式
    onMounted(() => {
      isTestMode.value = import.meta.env.MODE === 'development' ||
                        import.meta.env.VITE_APP_TEST_MODE === 'true';

      if (isTestMode.value) {
        fillCredentials('admin', 'admin123');
      }

      // 检查是否已登录 - 使用与user模块一致的key
      const token = localStorage.getItem('token');
      if (token) {
        // 直接跳转到首页，由路由守卫处理认证验证
        router.push('/dashboard');
      }
    });

    // 填充凭据函数
    const fillCredentials = (user, pass) => {
      username.value = user;
      password.value = pass;
    };

    // 处理登录
    const handleLogin = async () => {
      if (!username.value || !password.value) {
        errorMessage.value = '请输入用户名和密码';
        return;
      }

      isLoading.value = true;
      errorMessage.value = '';

      try {
        // 使用查询参数发送请求（根据后端API要求）
        const response = await request.post('/auth/login', null, {
          params: {
            username: username.value,
            password: password.value
          }
        });

        console.log('登录响应:', response);

        if (!response || !response.token) {
          throw new Error('无效的响应格式');
        }

        // 登录成功，使用Vuex action保存令牌和用户信息
        try {
          await store.dispatch('user/login', {
            username: username.value,
            password: password.value
          });
        } catch (error) {
          console.warn('Vuex登录失败，使用备用方案:', error);
          // Vuex登录失败时的备用方案
          localStorage.setItem('token', response.token);
          localStorage.setItem('user', JSON.stringify(response.user));
        }

        // 显示成功消息
        console.log('登录成功');

        // 立即跳转到首页
        router.push('/dashboard');
      } catch (error) {
        console.error('登录错误详情:', error);
        errorMessage.value = error.message || '登录失败，请稍后重试';
      } finally {
        isLoading.value = false;
      }
    };

    return {
      username,
      password,
      isLoading,
      errorMessage,
      isTestMode,
      handleLogin,
      fillCredentials
    };
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-form {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 400px;
}

h2 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: #333;
}

.form-group {
  margin-bottom: 1rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: #555;
}

input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

input:focus {
  outline: none;
  border-color: #667eea;
}

.error-message {
  color: #e74c3c;
  margin-bottom: 1rem;
  text-align: center;
}

.login-btn {
  width: 100%;
  padding: 0.75rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.3s;
}

.login-btn:hover:not(:disabled) {
  background: #5a67d8;
}

.login-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.test-mode-notice {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
  text-align: center;
}

.test-mode-notice p {
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: #667eea;
}

.test-mode-notice button {
  margin: 0.25rem;
  padding: 0.5rem;
  background: #f1f5f9;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
}

.test-mode-notice button:hover {
  background: #e2e8f0;
}
</style>