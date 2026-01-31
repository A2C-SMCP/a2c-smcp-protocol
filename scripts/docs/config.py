"""文档部署配置管理。

从环境变量加载部署配置。
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .version_utils import get_project_version


@dataclass
class DocServerConfig:
    """文档服务器配置。

    Attributes:
        host: 服务器主机地址或 IP
        port: SSH 端口，默认 22
        user: SSH 用户名，默认 root
        password: SSH 密码（可选，优先使用密钥）
        key_filename: SSH 私钥文件路径
        deploy_path: 文档部署路径
    """

    host: str
    port: int = 22
    user: str = "root"
    password: Optional[str] = None
    key_filename: Optional[str] = None
    deploy_path: str = "/var/www/doc.turingfocus.cn/a2c-smcp"


@dataclass
class WechatConfig:
    """企业微信通知配置。

    Attributes:
        webhook_url: 企业微信机器人 Webhook URL
    """

    webhook_url: str


@dataclass
class DeployConfig:
    """部署配置总入口。

    Attributes:
        server: 文档服务器配置
        wechat: 企业微信配置（可选）
        version: 当前文档版本
    """

    server: DocServerConfig
    wechat: Optional[WechatConfig] = None
    version: str = field(default_factory=get_project_version)

    @classmethod
    def from_env(cls) -> "DeployConfig":
        """从环境变量加载配置。

        环境变量列表:
            DOCS_SERVER_HOST: 服务器地址 (必需)
            DOCS_SERVER_PORT: SSH 端口 (默认 22)
            DOCS_SERVER_USER: SSH 用户名 (默认 root)
            DOCS_SERVER_PASSWORD: SSH 密码 (与 KEY_FILE 二选一)
            DOCS_SERVER_KEY_FILE: SSH 私钥路径 (与 PASSWORD 二选一)
            DOCS_DEPLOY_PATH: 部署路径 (默认 /var/www/doc.turingfocus.cn/a2c-smcp)
            WECOM_WEBHOOK_URL: 企业微信 Webhook (可选)

        Returns:
            DeployConfig: 加载的配置对象
        """
        server = DocServerConfig(
            host=os.getenv("DOCS_SERVER_HOST", ""),
            port=int(os.getenv("DOCS_SERVER_PORT", "22")),
            user=os.getenv("DOCS_SERVER_USER", "root"),
            password=os.getenv("DOCS_SERVER_PASSWORD"),
            key_filename=os.getenv("DOCS_SERVER_KEY_FILE"),
            deploy_path=os.getenv(
                "DOCS_DEPLOY_PATH", "/var/www/doc.turingfocus.cn/a2c-smcp"
            ),
        )

        wechat = None
        if os.getenv("WECOM_WEBHOOK_URL"):
            wechat = WechatConfig(webhook_url=os.getenv("WECOM_WEBHOOK_URL", ""))

        return cls(server=server, wechat=wechat)

    def validate(self) -> list[str]:
        """验证配置是否完整。

        Returns:
            list[str]: 错误信息列表，空列表表示验证通过
        """
        errors = []

        # 验证服务器配置
        if not self.server.host:
            errors.append("DOCS_SERVER_HOST 未设置")

        if not self.server.password and not self.server.key_filename:
            errors.append("DOCS_SERVER_PASSWORD 或 DOCS_SERVER_KEY_FILE 至少需要设置一个")

        return errors
