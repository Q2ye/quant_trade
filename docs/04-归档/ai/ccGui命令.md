## Claude Code 内置命令

| 命令 | 含义 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清除当前对话历史，重新开始 |
| `/compact` | 压缩上下文，自动摘要历史对话以释放 token 额度，防止上下文溢出 |
| `/config` | 打开/修改 Claude Code 配置（主题、模型等） |
| `/cost` | 查看当前会话的 token 用量和费用 |
| `/init` | 为当前项目初始化 CLAUDE.md 文件，生成项目文档 |
| `/upgrade` | 升级 Claude Code 版本（灰色=当前已是最新或不可用） |
| `/login` | 登录 Anthropic 账号 |
| `/logout` | 登出 Anthropic 账号 |
| `/doctor` | 诊断工具，检查 Claude Code 环境和配置是否存在问题 |
| `/status` | 查看当前会话状态（模型、分支、上下文使用量等） |
| `/tasks` | 查看/管理后台运行的任务 |

## 可用 Skills（自定义技能）

| 技能 | 含义 |
|------|------|
| `/quantsys-architect` | 量化系统架构师，遵循架构规范与开发铁律 |
| `/review` | 审查 Pull Request |
| `/security-review` | 对当前分支变更做安全审查 |
| `/simplify` | 审查代码的复用性、质量和效率 |
| `/update-config` | 配置 settings.json（权限、钩子、环境变量等） |
| `/keybindings-help` | 自定义键盘快捷键 |
| `/loop` | 定时循环执行某个命令 |
| `/fewer-permission-prompts` | 减少权限弹窗，将常用操作加入白名单 |
| `/claude-api` | 构建和调试 Anthropic SDK 应用 |
