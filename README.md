# A2C-SMCP Protocol Specification

A2C-SMCP (Agent To Computer SMCP) 是一种远程工具调用协议，定义了 Agent 与 Computer 之间通过 Socket.IO 进行通信的规范。

## 文档结构

- [协议概述](docs/specification/index.md) - 设计目标与核心概念
- [架构设计](docs/specification/architecture.md) - 角色关系与通信模型
- [事件定义](docs/specification/events.md) - 完整事件列表
- [数据结构](docs/specification/data-structures.md) - 请求/响应数据结构
- [房间模型](docs/specification/room-model.md) - 房间隔离机制
- [错误处理](docs/specification/error-handling.md) - 错误码与响应格式
- [安全考虑](docs/specification/security.md) - 安全性要求
- [FAQ](docs/appendix/faq.md) - 常见问题

## 在线文档

访问 [https://doc.turingfocus.cn/a2c-smcp/](https://doc.turingfocus.cn/a2c-smcp/) 查看在线文档。

## SDK 实现

| 语言 | 仓库 | 状态 |
|------|------|------|
| Python | [python-sdk](https://github.com/A2C-SMCP/python-sdk) | RC |
| Rust | [rust-sdk](https://github.com/A2C-SMCP/rust-sdk) | 开发中 |

## 版本

当前协议版本: **0.1.2-rc1**

---

## 开发指南

### 环境准备

本项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖。

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或 macOS: brew install uv

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装文档依赖
uv pip install -e ".[docs]"
```

> **备选方案**：如果不使用 uv，也可以用标准 pip：
> ```bash
> python -m venv .venv && source .venv/bin/activate
> pip install -e ".[docs]"
> ```

### 本地预览

```bash
# 启动开发服务器（实时热重载）
inv docs.serve

# 访问 http://127.0.0.1:8000
```

### 构建文档

```bash
# 构建当前版本（版本号从 pyproject.toml 自动读取）
inv docs.build

# 构建指定版本
inv docs.build --version 0.1.2-rc1

# 预览多版本文档
inv docs.serve-versioned
```

### 部署文档

```bash
# 完整部署流程（构建 + 推送 + 服务器更新）
inv docs.deploy

# 仅构建，不推送
inv docs.deploy --push=false
```

### 可用命令

```bash
inv --list                  # 查看所有可用任务
inv docs.serve              # 本地预览（实时热重载）
inv docs.serve-versioned    # 多版本预览
inv docs.build              # 构建文档
inv docs.deploy             # 部署到服务器
inv docs.clean              # 清理构建产物
inv docs.server-setup       # 查看服务器初始化步骤
```

---

## 部署配置

### 环境变量

部署脚本通过环境变量配置，建议创建 `.env` 文件（已在 .gitignore 中排除）：

```bash
# .env 文件示例

# ========== 必需配置 ==========

# 文档服务器地址
DOCS_SERVER_HOST=118.195.182.52

# SSH 认证（二选一）
DOCS_SERVER_PASSWORD=your_password
# 或使用密钥文件
# DOCS_SERVER_KEY_FILE=~/.ssh/id_rsa

# ========== 可选配置 ==========

# SSH 端口（默认 22）
DOCS_SERVER_PORT=22

# SSH 用户名（默认 root）
DOCS_SERVER_USER=root

# 部署路径（默认 /var/www/doc.turingfocus.cn/a2c-smcp）
DOCS_DEPLOY_PATH=/var/www/doc.turingfocus.cn/a2c-smcp

# 企业微信通知（可选）
# WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

### 加载环境变量

```bash
# 方式1: 使用 dotenv
pip install python-dotenv
# 在脚本中会自动加载 .env 文件

# 方式2: 手动 export
source .env

# 方式3: 临时设置
DOCS_SERVER_HOST=xxx inv docs.deploy
```

### 首次部署

首次部署前需要在服务器上初始化环境：

```bash
# 查看初始化步骤
inv docs.server-setup
```

服务器端操作：

```bash
# 1. SSH 登录服务器
ssh root@118.195.182.52

# 2. 创建文档目录
cd /var/www/doc.turingfocus.cn/
git clone -b gh-pages https://github.com/A2C-SMCP/a2c-smcp-protocol.git a2c-smcp
chown -R nginx:nginx /var/www/doc.turingfocus.cn/a2c-smcp
chmod -R 755 /var/www/doc.turingfocus.cn/a2c-smcp

# 3. 更新 Nginx 配置
# 在 /etc/nginx/conf.d/doc.turingfocus.cn.conf 添加:
#
# location /a2c-smcp/ {
#     alias /var/www/doc.turingfocus.cn/a2c-smcp/;
#     try_files $uri $uri/ /a2c-smcp/latest/index.html;
#     index index.html;
# }

# 4. 测试并重载 Nginx
nginx -t && systemctl reload nginx
```

---

## 版本管理

本项目使用 [mike](https://github.com/jimporter/mike) 进行多版本文档管理：

- 每个版本独立部署到 `gh-pages` 分支
- `latest` 别名指向最新版本
- 文档内置版本切换器

### 版本发布流程

```bash
# 1. 更新 pyproject.toml 中的版本号
# 2. 构建并部署
inv docs.deploy

# 或使用 bump-my-version 自动更新版本
pip install bump-my-version
bump-my-version bump patch  # 0.1.2 -> 0.1.3
bump-my-version bump minor  # 0.1.2 -> 0.2.0
bump-my-version bump major  # 0.1.2 -> 1.0.0
```

---

## 项目结构

```
a2c-smcp-protocol/
├── docs/                      # 文档源文件
│   ├── index.md              # 首页
│   ├── specification/        # 协议规范
│   │   ├── index.md          # 概述
│   │   ├── architecture.md   # 架构设计
│   │   ├── events.md         # 事件定义
│   │   ├── data-structures.md# 数据结构
│   │   ├── room-model.md     # 房间模型
│   │   ├── error-handling.md # 错误处理
│   │   └── security.md       # 安全考虑
│   └── appendix/
│       └── faq.md            # 常见问题
├── scripts/                   # 部署脚本
│   └── docs/
│       ├── __init__.py
│       ├── config.py         # 配置管理
│       ├── tasks.py          # Invoke 任务
│       └── version_utils.py  # 版本工具
├── mkdocs.yml                # MkDocs 配置
├── pyproject.toml            # 项目配置
├── tasks.py                  # Invoke 入口
├── CLAUDE.md                 # Claude Code 指南
└── README.md                 # 本文件
```

---

## License

MIT
