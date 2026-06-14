<template>
  <div class="register-container">
    <div class="register-form">
      <h2>创建账号</h2>
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
        <label for="email">邮箱</label>
        <input
          type="email"
          id="email"
          v-model="email"
          placeholder="请输入邮箱（选填）"
          :disabled="isLoading"
        />
      </div>
      <div class="form-group">
        <label for="password">密码</label>
        <input
          type="password"
          id="password"
          v-model="password"
          placeholder="请输入密码（至少8位，含大小写字母、数字、特殊字符）"
          :disabled="isLoading"
        />
      </div>
      <div class="form-group">
        <label for="confirmPassword">确认密码</label>
        <input
          type="password"
          id="confirmPassword"
          v-model="confirmPassword"
          placeholder="请再次输入密码"
          :disabled="isLoading"
          @keyup.enter="handleRegister"
        />
      </div>
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>
      <div v-if="successMessage" class="success-message">
        {{ successMessage }}
      </div>
      <button
        class="register-btn"
        :disabled="isLoading"
        @click="handleRegister"
      >
        {{ isLoading ? "注册中..." : "注册" }}
      </button>
      <div class="login-link">
        <span>已有账号？</span>
        <a @click="goToLogin">去登录</a>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from "vue";
import { useRouter } from "vue-router";
import request from "@/utils/request";

export default {
  name: "Register",
  setup() {
    const username = ref("");
    const email = ref("");
    const password = ref("");
    const confirmPassword = ref("");
    const isLoading = ref(false);
    const errorMessage = ref("");
    const successMessage = ref("");
    const router = useRouter();

    const goToLogin = () => {
      router.push("/login");
    };

    const handleRegister = async () => {
      errorMessage.value = "";
      successMessage.value = "";

      if (!username.value || !password.value || !confirmPassword.value) {
        errorMessage.value = "请填写必填字段";
        return;
      }

      if (password.value !== confirmPassword.value) {
        errorMessage.value = "两次输入的密码不一致";
        return;
      }

      if (password.value.length < 8) {
        errorMessage.value = "密码长度至少为8位";
        return;
      }

      isLoading.value = true;

      try {
        await request.post("/quantTrade/system/auth/register", {
          username: username.value,
          email: email.value,
          password: password.value,
        });

        successMessage.value = "注册成功，即将跳转到登录页...";
        setTimeout(() => {
          router.push("/login");
        }, 1500);
      } catch (error) {
        if (error.response && error.response.data) {
          const detail = error.response.data.detail;
          errorMessage.value =
            typeof detail === "string" ? detail : "注册失败，请稍后重试";
        } else {
          errorMessage.value = error.message || "注册失败，请稍后重试";
        }
      } finally {
        isLoading.value = false;
      }
    };

    return {
      username,
      email,
      password,
      confirmPassword,
      isLoading,
      errorMessage,
      successMessage,
      handleRegister,
      goToLogin,
    };
  },
};
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: var(--vh-full);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-form {
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

.success-message {
  color: #27ae60;
  margin-bottom: 1rem;
  text-align: center;
}

.register-btn {
  width: 100%;
  padding: 0.75rem;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.3s;
}

.register-btn:hover:not(:disabled) {
  background: #219a52;
}

.register-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.login-link {
  margin-top: 1rem;
  text-align: center;
  font-size: 0.9rem;
  color: #888;
}

.login-link a {
  color: #667eea;
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
}

.login-link a:hover {
  text-decoration: underline;
}
</style>
