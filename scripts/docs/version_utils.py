"""版本号读取工具。

从 pyproject.toml 动态读取项目版本号，作为文档系统的单一真实来源。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

# 缓存版本号，避免重复读取
_CACHED_VERSION: str | None = None

# 项目根目录
PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.parent
PYPROJECT_TOML: Final[Path] = PROJECT_ROOT / "pyproject.toml"


def get_project_version() -> str:
    """从 pyproject.toml 读取项目版本号。

    Returns:
        str: 项目版本号，如 "0.1.2-rc1"

    Raises:
        FileNotFoundError: pyproject.toml 不存在
        RuntimeError: 无法解析版本号
    """
    global _CACHED_VERSION

    # 使用缓存
    if _CACHED_VERSION is not None:
        return _CACHED_VERSION

    # 检查文件是否存在
    if not PYPROJECT_TOML.exists():
        raise FileNotFoundError(
            f"pyproject.toml not found at {PYPROJECT_TOML}. "
            "Are you in the correct directory?"
        )

    # 方法1: 使用 tomli 解析
    try:
        import tomli

        with PYPROJECT_TOML.open("rb") as f:
            data = tomli.load(f)

        version = data["project"]["version"]

        if not isinstance(version, str):
            raise RuntimeError(f"Version must be a string, got {type(version)}")

        _CACHED_VERSION = version
        return version

    except ImportError:
        # tomli 不可用，回退到简单文本解析
        pass
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Failed to parse version from pyproject.toml: {e}") from e

    # 方法2: 回退到简单文本解析
    try:
        content = PYPROJECT_TOML.read_text(encoding="utf-8")

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith('version = "'):
                # 提取引号中的版本号
                version = line.split('"')[1]
                _CACHED_VERSION = version
                return version
            elif line.startswith("version = '"):
                # 提取单引号中的版本号
                version = line.split("'")[1]
                _CACHED_VERSION = version
                return version

        raise RuntimeError("Version field not found in pyproject.toml")

    except Exception as e:
        raise RuntimeError(f"Failed to parse version from pyproject.toml: {e}") from e


def clear_version_cache() -> None:
    """清除版本缓存。

    主要用于测试场景，确保每次读取都是最新的版本号。
    """
    global _CACHED_VERSION
    _CACHED_VERSION = None


def normalize_version(version: str) -> str:
    """规范化版本号格式。

    将 "0.1.2rc1" 转换为 "0.1.2-rc1" 格式。

    Args:
        version: 原始版本号

    Returns:
        str: 规范化后的版本号
    """
    # 将 "0.1.2rc1" 转换为 "0.1.2-rc1"
    return re.sub(r"(\d+)(rc|alpha|beta)(\d+)", r"\1-\2\3", version, count=1)


if __name__ == "__main__":
    # 命令行支持
    try:
        version = get_project_version()
        print(version)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
