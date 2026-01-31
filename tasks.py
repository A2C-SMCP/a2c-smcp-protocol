"""Invoke 任务入口文件。

此文件作为 Invoke 的任务集合入口，导入所有任务模块。

使用方式:
    inv --list              # 查看所有可用任务
    inv docs.serve          # 本地预览文档
    inv docs.build          # 构建文档
    inv docs.deploy         # 部署文档到服务器
    inv docs.clean          # 清理构建产物
    inv docs.server-setup   # 查看服务器初始化步骤
"""

from invoke import Collection

from scripts.docs import tasks as docs_tasks

# 创建文档任务集合
ns = Collection()
ns.add_collection(Collection.from_module(docs_tasks), name="docs")
