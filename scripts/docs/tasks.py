"""Invoke 任务定义 - 文档构建与部署。

提供命令行接口来管理文档构建和部署。

使用方式:
    inv docs.serve          # 本地预览
    inv docs.build          # 构建文档
    inv docs.deploy         # 部署到服务器
    inv docs.clean          # 清理构建产物
"""

import sys

from invoke import task

from .config import DeployConfig
from .version_utils import get_project_version

# 加载配置
config = DeployConfig.from_env()


@task
def build(c, version=None, alias="latest"):
    """构建文档（使用 mike 标准流程）。

    Args:
        version: 版本号 (如 '0.1.2-rc1')，不指定则使用 pyproject.toml 中的版本
        alias: 版本别名 (如 'latest', 'stable')，默认 'latest'。设为空字符串禁用别名
    """
    target_version = version or get_project_version()

    print(f"🔨 构建文档 (version={target_version}, alias={alias})")

    # 使用 mike 标准命令（部署到本地 gh-pages 分支）
    cmd_parts = ["mike", "deploy", target_version]
    if alias and alias.strip():
        cmd_parts.append(alias)
    cmd_parts.extend(["--update-aliases"])

    c.run(" ".join(cmd_parts), warn=False)
    print("✅ 文档构建完成")


@task
def serve(c):
    """启动本地开发服务器。"""
    print("🚀 启动 MkDocs 开发服务器 (http://127.0.0.1:8000)")
    # pty=True 支持交互式输出和颜色
    c.run("mkdocs serve", pty=True)


@task
def serve_versioned(c):
    """启动多版本文档预览服务器。"""
    print("🚀 启动 Mike 多版本服务器 (http://127.0.0.1:8000)")
    c.run("mike serve", pty=True)


def sync_gh_pages(c):
    """同步远程 gh-pages 分支到本地。

    在多人协作场景下，先同步远程分支可避免推送时的 non-fast-forward 冲突。
    """
    print("🔄 同步远程 gh-pages 分支...")

    # 检查远程 gh-pages 分支是否存在
    result = c.run("git ls-remote --heads origin gh-pages", warn=True, hide=True)
    if not result.stdout.strip():
        print("   远程 gh-pages 分支不存在，跳过同步（首次部署）")
        return

    # 获取远程分支最新状态
    c.run("git fetch origin gh-pages:gh-pages", warn=True)
    print("   ✅ 同步完成")


@task
def deploy(c, version=None, alias="latest", push=True):
    """部署文档（使用 mike + Git 标准流程）。

    工作流程:
        1. 同步远程 gh-pages 分支
        2. 使用 mike 构建指定版本
        3. 推送到 GitHub
        4. 触发服务器 git pull 更新

    Args:
        version: 版本号（可选，默认使用 pyproject.toml 中的版本）
        alias: 版本别名（默认 'latest'）
        push: 是否推送到远程仓库（默认 True）
    """
    target_version = version or get_project_version()

    print(f"🚀 部署文档 (version={target_version})")

    # 验证配置
    errors = config.validate()
    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"   - {error}")
        sys.exit(1)

    # 0. 同步远程 gh-pages 分支（避免多人协作冲突）
    sync_gh_pages(c)

    # 1. 构建（mike deploy 到本地 gh-pages 分支）
    build(c, version=target_version, alias=alias)

    # 2. 推送到 GitHub
    if push:
        print("📤 推送到 GitHub...")
        c.run("git push origin gh-pages", warn=False)
    else:
        print("⚠️  跳过 Git 推送 (--push=false)")

    # 3. 触发服务器更新（通过 SSH）
    print("🔄 触发服务器更新...")
    update_server()

    # 4. 发送通知（如果配置了）
    if config.wechat:
        notify_wechat(
            f"✅ A2C-SMCP 文档部署成功\n"
            f"版本: {target_version}\n"
            f"别名: {alias}\n"
            f"服务器: {config.server.host}\n"
            f"路径: {config.server.deploy_path}"
        )

    print("✅ 部署完成")


@task
def server_setup(c):
    """显示服务器初始化步骤。

    首次部署前需要在服务器上执行的操作。
    """
    print("🖥️  服务器初始化步骤：")
    print()
    print("1. SSH 登录服务器：")
    print("   ssh root@<YOUR_SERVER_IP>")
    print()
    print("2. 创建文档目录并克隆 gh-pages 分支：")
    print("   cd /var/www/doc.turingfocus.cn/")
    print(
        "   git clone -b gh-pages https://github.com/A2C-SMCP/a2c-smcp-protocol.git a2c-smcp"
    )
    print("   chown -R nginx:nginx /var/www/doc.turingfocus.cn/a2c-smcp")
    print("   chmod -R 755 /var/www/doc.turingfocus.cn/a2c-smcp")
    print()
    print("3. 更新 Nginx 配置 (/etc/nginx/conf.d/doc.turingfocus.cn.conf)：")
    print("   添加 location /a2c-smcp/ 配置块")
    print()
    print("4. 更新门户首页 (/var/www/doc.turingfocus.cn/index.html)：")
    print("   添加 A2C-SMCP 文档入口链接")
    print()
    print("5. 重载 Nginx：")
    print("   nginx -t && systemctl reload nginx")


@task
def clean(c):
    """清理构建产物。"""
    c.run("rm -rf site/", warn=False)
    print("✅ 清理完成")


@task
def update_server_task(c):
    """触发服务器更新（Git pull）。"""
    update_server()


def update_server():
    """触发服务器 Git pull 更新文档。

    使用 SSH 连接到服务器并执行 Git pull。
    """
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # 连接服务器
        if config.server.password:
            ssh.connect(
                config.server.host,
                port=config.server.port,
                username=config.server.user,
                password=config.server.password,
            )
        elif config.server.key_filename:
            ssh.connect(
                config.server.host,
                port=config.server.port,
                username=config.server.user,
                key_filename=config.server.key_filename,
            )
        else:
            print("⚠️  未配置密码或密钥文件，跳过服务器更新")
            return

        # 执行 Git pull
        stdin, stdout, stderr = ssh.exec_command(
            f"cd {config.server.deploy_path} && git pull origin gh-pages"
        )

        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode()
        error = stderr.read().decode()

        if exit_code == 0:
            print(f"✅ 服务器更新成功:\n{output}")
        else:
            print(f"⚠️  服务器更新警告:\n{error}")

    except Exception as e:
        print(f"❌ 服务器更新失败: {e}")
    finally:
        ssh.close()


def notify_wechat(message: str):
    """发送企业微信通知。

    Args:
        message: 通知消息内容
    """
    if config.wechat:
        import requests

        try:
            requests.post(
                config.wechat.webhook_url,
                json={"msgtype": "text", "text": {"content": message}},
            )
        except Exception as e:
            print(f"⚠️  企业微信通知失败: {e}")
