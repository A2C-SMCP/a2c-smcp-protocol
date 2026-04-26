"""Invoke 任务定义 - 文档构建与部署。

提供命令行接口来管理文档构建和部署。

使用方式:
    inv docs.serve                    # 本地预览
    inv docs.build                    # 构建文档
    inv docs.deploy                   # 部署到公司服务器（默认 mode=git）
    inv docs.deploy --mode=upload     # 服务器拉 GitHub 网络不稳时使用本地打包 SFTP 上传
    inv docs.deploy-github            # 部署到 GitHub Pages
    inv docs.clean                    # 清理构建产物
"""

import os
import sys
import tempfile
import time

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
def deploy(c, version=None, alias="latest", push=True, mode="git"):
    """部署文档（使用 mike + Git 标准流程）。

    工作流程:
        1. 同步远程 gh-pages 分支
        2. 使用 mike 构建指定版本
        3. 推送到 GitHub
        4. 触发服务器更新（按 mode 选择）

    Args:
        version: 版本号（可选，默认使用 pyproject.toml 中的版本）
        alias: 版本别名（默认 'latest'）
        push: 是否推送到远程仓库（默认 True）
        mode: 服务器更新模式，'git'（默认）或 'upload'。
              git: 服务器 ssh 执行 git fetch + reset --hard origin/gh-pages，需要服务器到 GitHub 网络通畅
              upload: 本地打包 → SFTP 上传 → 远端解压覆盖，绕开服务器 git pull（GitHub 网络不稳时使用）
    """
    if mode not in ("git", "upload"):
        print(f"❌ 未知 mode: {mode}（仅支持 'git' 或 'upload'）")
        sys.exit(1)

    target_version = version or get_project_version()

    print(f"🚀 部署文档 (version={target_version}, mode={mode})")

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

    # 3. 触发服务器更新
    print(f"🔄 触发服务器更新 (mode={mode})...")
    if mode == "upload":
        upload_server(c)
    else:
        update_server()

    # 4. 发送通知（如果配置了）
    if config.wechat:
        notify_wechat(
            f"✅ A2C-SMCP 文档部署成功\n"
            f"版本: {target_version}\n"
            f"别名: {alias}\n"
            f"模式: {mode}\n"
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
    print("   cd a2c-smcp")
    print("   chown -R nginx:nginx .")
    print("   # 按类型设置权限（避免文件被加 +x 触发 git mode dirty）")
    print("   find . -path ./.git -prune -o -type d -exec chmod 755 {} +")
    print("   find . -path ./.git -prune -o -type f -exec chmod 644 {} +")
    print("   # 让 git 永久忽略 mode 差异（兜底）")
    print("   git config core.fileMode false")
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
    """单独触发服务器 git fetch + reset --hard 更新（mode=git）。"""
    update_server()


@task(name="upload-server")
def upload_server_task(c):
    """单独触发本地打包 + SFTP 上传 + 远端覆盖部署（mode=upload）。

    适用于服务器到 GitHub 网络不稳定的场景。
    需要本地已经构建好 gh-pages 分支（即先跑过 inv docs.build）。
    """
    upload_server(c)


def _connect_ssh():
    """打开 SSH 连接（公共函数）。

    Returns:
        paramiko.SSHClient | None: 已连接的客户端；未配置凭证时返回 None
    """
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

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
        ssh.close()
        return None
    return ssh


def _exec_remote(ssh, cmd, *, on_fail_exit=True):
    """在已连接的 SSH 会话上执行命令。

    Args:
        ssh: 已连接的 paramiko.SSHClient
        cmd: 要执行的命令
        on_fail_exit: 失败时是否调用 sys.exit(1)（默认 True）

    Returns:
        (exit_code, stdout, stderr)
    """
    _, stdout, stderr = ssh.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    if exit_code != 0:
        print(f"❌ 远端命令失败 (exit {exit_code}):")
        print(f"   命令: {cmd}")
        if out:
            print(f"   STDOUT:\n{out}")
        if err:
            print(f"   STDERR:\n{err}")
        if on_fail_exit:
            sys.exit(1)
    return exit_code, out, err


def update_server():
    """通过 SSH fetch + reset --hard 同步服务器 git checkout。

    服务器侧 deploy_path 是 gh-pages 分支的镜像，权威源是 origin/gh-pages。
    使用 reset --hard 而非 pull，避免文件 mode/dirty state 阻塞合并。
    失败时 sys.exit(1)。
    """
    try:
        ssh = _connect_ssh()
    except Exception as e:
        print(f"❌ SSH 连接失败: {e}")
        sys.exit(1)
    if ssh is None:
        print("⚠️  未配置密码或密钥文件，跳过服务器更新")
        return

    try:
        cmd = (
            f"cd {config.server.deploy_path} && "
            f"git config core.fileMode false && "
            f"git fetch origin gh-pages && "
            f"git reset --hard origin/gh-pages"
        )
        _, out, _ = _exec_remote(ssh, cmd)
        print(f"✅ 服务器更新成功 (mode=git):\n{out}")
    finally:
        ssh.close()


def upload_server(c):
    """本地打包 + SFTP 上传 + 远端覆盖部署。

    用于服务器到 GitHub 的网络不稳定场景，绕开服务器 git pull。流程：
        1. 本地从 gh-pages 分支创建 worktree
        2. 本地 tar 打包（排除 .git）
        3. SFTP 上传 tar 到服务器 /tmp
        4. 远端解压覆盖 deploy_path（保留 .git 不动）+ 修正权限
        5. 清理本地 worktree / tar 与远端 tar

    保留服务器 .git 但 working tree 会与 .git HEAD 偏离。下次走 mode=git 时
    update_server 的 reset --hard 会重新对齐。
    """
    try:
        ssh = _connect_ssh()
    except Exception as e:
        print(f"❌ SSH 连接失败: {e}")
        sys.exit(1)
    if ssh is None:
        print("⚠️  未配置密码或密钥文件，跳过服务器更新")
        return

    deploy_path = config.server.deploy_path
    nginx_user = config.server.nginx_user
    timestamp = int(time.time())
    worktree = tempfile.mkdtemp(prefix="a2c-gh-pages-")
    local_tar = f"/tmp/a2c-smcp-{timestamp}.tar.gz"
    remote_tar = f"/tmp/a2c-smcp-{timestamp}.tar.gz"

    # 安全门控：拒绝 deploy_path 不含 'a2c-smcp' 标识符的部署（防误删/误改）
    if "a2c-smcp" not in deploy_path:
        print(f"❌ deploy_path 缺少 'a2c-smcp' 标识符，拒绝部署: {deploy_path}")
        sys.exit(1)

    try:
        # 1. 本地从 gh-pages 创建 worktree
        print(f"🔄 创建 gh-pages worktree: {worktree}")
        c.run(f"git worktree add {worktree} gh-pages", warn=False)

        # 2. 本地打包（排除 .git，避免上传 git metadata）
        print(f"📦 本地打包: {local_tar}")
        c.run(
            f"tar --exclude='./.git' -czf {local_tar} -C {worktree} .",
            warn=False,
        )

        # 3. SFTP 上传
        print(f"📤 SFTP 上传到 {config.server.host}:{remote_tar}")
        sftp = ssh.open_sftp()
        try:
            sftp.put(local_tar, remote_tar)
        finally:
            sftp.close()

        # 4. 远端解压覆盖 + 修正权限
        # 保留 deploy_path/.git 不动；只覆盖静态产物文件
        # 用 find -path ./.git -prune 跳过 .git 目录，避免改 git 内部权限
        cmd = (
            # sanity check：路径存在且非空（防止配置错误把 tar 解压到无关目录）
            f'test -d {deploy_path} && test -n "$(ls -A {deploy_path} 2>/dev/null)" '
            f'|| {{ echo "ERROR: deploy_path missing or empty: {deploy_path}"; exit 1; }} && '
            f"cd {deploy_path} && "
            # 解压覆盖（tar 默认覆盖同名文件，不删除多余文件——多版本目录由 mike 管理）
            f"tar -xzf {remote_tar} && "
            # 修正所有权
            f"chown -R {nginx_user}:{nginx_user} {deploy_path} && "
            # 修正权限（目录 755 / 文件 644，跳过 .git 内部）
            f"find {deploy_path} -path '{deploy_path}/.git' -prune -o -type d -print0 "
            f"  | xargs -0 -r chmod 755 && "
            f"find {deploy_path} -path '{deploy_path}/.git' -prune -o -type f -print0 "
            f"  | xargs -0 -r chmod 644 && "
            # 持久关闭 fileMode 检查，下次走 mode=git 不会再因 mode 误判 dirty
            f"git -C {deploy_path} config core.fileMode false && "
            # 清理远端 tar
            f"rm -f {remote_tar}"
        )
        _, out, _ = _exec_remote(ssh, cmd)
        print(f"✅ 服务器更新成功 (mode=upload):\n{out}")
    finally:
        # 清理本地资源
        try:
            c.run(f"git worktree remove --force {worktree}", warn=True)
        except Exception:
            pass
        try:
            os.unlink(local_tar)
        except FileNotFoundError:
            pass
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


# GitHub Pages 相关配置
GITHUB_PAGES_URL = "https://a2c-smcp.github.io/a2c-smcp-protocol/"


@task(name="deploy-github")
def deploy_github(c, version=None, alias="latest", set_default=True):
    """部署文档到 GitHub Pages。

    工作流程:
        1. 同步远程 gh-pages 分支
        2. 使用 mike 构建指定版本
        3. 设置默认版本
        4. 推送到 GitHub（自动触发 GitHub Pages 部署）

    Args:
        version: 版本号（可选，默认使用 pyproject.toml 中的版本）
        alias: 版本别名（默认 'latest'）
        set_default: 是否设置为默认版本（默认 True）
    """
    target_version = version or get_project_version()

    print(f"🚀 部署文档到 GitHub Pages (version={target_version})")
    print(f"   目标 URL: {GITHUB_PAGES_URL}")

    # 0. 同步远程 gh-pages 分支
    sync_gh_pages(c)

    # 1. 构建（mike deploy 到本地 gh-pages 分支）
    build(c, version=target_version, alias=alias)

    # 2. 设置默认版本
    if set_default:
        print(f"📌 设置默认版本为 '{alias}'...")
        c.run(f"mike set-default {alias}", warn=True)

    # 3. 推送到 GitHub
    print("📤 推送到 GitHub...")
    c.run("git push origin gh-pages", warn=False)

    print(f"✅ GitHub Pages 部署完成")
    print(f"   文档将在几分钟后可访问: {GITHUB_PAGES_URL}")


@task(name="deploy-all")
def deploy_all(c, version=None, alias="latest", mode="git"):
    """同时部署到 GitHub Pages 和公司服务器。

    Args:
        version: 版本号（可选，默认使用 pyproject.toml 中的版本）
        alias: 版本别名（默认 'latest'）
        mode: 公司服务器更新模式，'git'（默认）或 'upload'。详见 deploy task
    """
    if mode not in ("git", "upload"):
        print(f"❌ 未知 mode: {mode}（仅支持 'git' 或 'upload'）")
        sys.exit(1)

    target_version = version or get_project_version()

    print(f"🚀 部署文档到所有目标 (version={target_version}, server mode={mode})")
    print()

    # 1. 部署到 GitHub Pages
    print("=" * 50)
    print("📦 Step 1: 部署到 GitHub Pages")
    print("=" * 50)
    deploy_github(c, version=target_version, alias=alias)
    print()

    # 2. 触发公司服务器更新
    print("=" * 50)
    print(f"📦 Step 2: 更新公司服务器 (mode={mode})")
    print("=" * 50)

    # 验证服务器配置
    errors = config.validate()
    if errors:
        print("⚠️  公司服务器配置不完整，跳过服务器更新:")
        for error in errors:
            print(f"   - {error}")
    else:
        if mode == "upload":
            upload_server(c)
        else:
            update_server()
        if config.wechat:
            notify_wechat(
                f"✅ A2C-SMCP 文档部署成功\n"
                f"版本: {target_version}\n"
                f"别名: {alias}\n"
                f"模式: {mode}\n"
                f"GitHub Pages: {GITHUB_PAGES_URL}\n"
                f"公司服务器: {config.server.host}"
            )

    print()
    print("✅ 全部部署完成")
