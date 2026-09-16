"""
ToolRegistry — 统一工具注册表

聚合内置工具 + MCP 远程工具，提供统一的查询、执行、schema 导出能力。
支持工具结果短期缓存（30秒），减少重复 DB 查询。
"""
import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agents.tools.base import BaseTool

logger = logging.getLogger(__name__)

# 工具结果缓存 TTL（秒）
TOOL_CACHE_TTL = 30


class ToolRegistry:
    """统一工具注册表"""

    def __init__(self):
        self._builtin: Dict[str, BaseTool] = {}
        self._mcp_tools: Dict[str, BaseTool] = {}  # 外部 MCP 工具，key 带命名空间
        self._mcp_tool_projects: Dict[str, Optional[int]] = {}  # MCP 工具名 → project_id（None=全局）
        self._cache: Dict[str, Dict[str, Any]] = {}  # {cache_key: {"result": ..., "expire_at": ...}}

    # ---------- 注册 ----------

    def register(self, tool: BaseTool):
        """注册内置工具"""
        self._builtin[tool.name] = tool
        logger.info(f"注册工具: {tool.name} ({tool.category})")

    def unregister(self, tool_name: str):
        """注销工具（用于 Skill 脚本临时工具的清理）"""
        if tool_name in self._builtin:
            del self._builtin[tool_name]
            logger.info(f"注销工具: {tool_name}")

    def register_mcp_tool(self, connector_name: str, tool: BaseTool, project_id: Optional[int] = None):
        """注册外部 MCP 工具，自动加命名空间前缀"""
        namespaced_name = f"{connector_name}__{tool.name}"
        tool.name = namespaced_name
        self._mcp_tools[namespaced_name] = tool
        self._mcp_tool_projects[namespaced_name] = project_id
        logger.info(f"注册 MCP 工具: {namespaced_name} (project_id={project_id})")

    def unregister_mcp_tools(self, connector_name: str):
        """移除某个连接器的所有 MCP 工具"""
        prefix = f"{connector_name}__"
        to_remove = [k for k in self._mcp_tools if k.startswith(prefix)]
        for k in to_remove:
            del self._mcp_tools[k]
            self._mcp_tool_projects.pop(k, None)
        logger.info(f"移除 MCP 工具: {len(to_remove)} 个 (连接器: {connector_name})")

    # ---------- 查询 ----------

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具（先查内置，再查 MCP）"""
        return self._builtin.get(name) or self._mcp_tools.get(name)

    def list_tools(self, project_id: Optional[int] = None) -> List[BaseTool]:
        """列出所有可用工具（内置工具全局可用，MCP 工具按 project_id 过滤）"""
        tools = list(self._builtin.values())
        for name, tool in self._mcp_tools.items():
            tool_project = self._mcp_tool_projects.get(name)
            # 全局工具（project_id=None）或匹配当前项目的工具可用
            if tool_project is None or tool_project == project_id:
                tools.append(tool)
        return tools

    def list_builtin_tools(self) -> List[BaseTool]:
        """仅列出内置工具"""
        return list(self._builtin.values())

    def list_mcp_tools(self, connector_name: Optional[str] = None) -> List[BaseTool]:
        """列出 MCP 工具，可按连接器过滤"""
        if connector_name:
            prefix = f"{connector_name}__"
            return [t for t in self._mcp_tools.values() if t.name.startswith(prefix)]
        return list(self._mcp_tools.values())

    def get_function_schemas(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有工具的 Function Calling schema（用于 bind_tools）"""
        return [t.to_function_schema() for t in self.list_tools(project_id)]

    def get_tool_names(self) -> List[str]:
        """获取所有工具名称（用于 Skill 白名单校验）"""
        return list(self._builtin.keys()) + list(self._mcp_tools.keys())

    # ---------- 执行 ----------

    async def execute(
        self,
        name: str,
        args: Dict[str, Any],
        db: Session,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        执行工具，统一返回 {"success": bool, "result": any or "error": str}
        所有工具统一 offload 到线程池，避免同步 DB 查询阻塞事件循环。
        """
        tool = self.get(name)
        if not tool:
            return {"success": False, "error": f"工具不存在: {name}"}

        try:
            if user_id and "user_id" not in args:
                args = {**args, "user_id": user_id}

            # P3: 工具结果短期缓存（只读类工具）
            cache_key = self._cache_key(name, args, project_id)
            cached = self._cache_get(cache_key)
            if cached is not None:
                logger.debug(f"工具缓存命中: {name}")
                return cached

            # 方案A：统一 offload 到线程池
            result = await asyncio.to_thread(
                self._run_tool_sync, tool, args, db, project_id, user_id
            )

            if isinstance(result, dict) and result.get("error"):
                return {"success": False, "error": result["error"]}

            final_result = {"success": True, "result": result}
            # 只读工具缓存结果
            if self._is_readonly_tool(name):
                self._cache_set(cache_key, final_result)
            return final_result
        except Exception as e:
            logger.error(f"工具执行失败: {name}, error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ---------- 缓存 ----------

    @staticmethod
    def _cache_key(name: str, args: Dict, project_id: Optional[int]) -> str:
        raw = json.dumps({"name": name, "args": args, "pid": project_id}, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_get(self, key: str) -> Optional[Dict]:
        item = self._cache.get(key)
        if item and item["expire_at"] > time.time():
            return item["result"]
        if key in self._cache:
            del self._cache[key]
        return None

    def _cache_set(self, key: str, result: Dict):
        self._cache[key] = {"result": result, "expire_at": time.time() + TOOL_CACHE_TTL}
        # 简单清理：超过100条时清理过期项
        if len(self._cache) > 100:
            now = time.time()
            self._cache = {k: v for k, v in self._cache.items() if v["expire_at"] > now}

    @staticmethod
    def _is_readonly_tool(name: str) -> bool:
        """判断是否为只读工具（可缓存）"""
        return not name.startswith("create_") and not name.startswith("update_") \
            and not name.startswith("delete_") and not name.startswith("execute_")

    @staticmethod
    def _run_tool_sync(tool, args: Dict[str, Any], db: Session,
                       project_id: Optional[int], user_id: Optional[int]):
        """在独立线程中运行 async 工具（统一异步桥接，规避事件循环冲突）"""
        from app.core.async_runner import run_async
        return run_async(tool.execute, args, db, project_id, user_id)


# 全局单例
tool_registry = ToolRegistry()
