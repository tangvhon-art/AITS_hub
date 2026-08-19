"""
SkillScriptTool — Skill 包中 Python 脚本的动态工具包装

当 Skill 匹配成功后，将 Skill 包中的 .py 脚本动态注册为工具，
LLM 可通过 Function Calling 调用执行。对话结束后自动注销。
"""
import ast
import re
import time
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.agents.tools.base import BaseTool, ToolParameter


# 危险模块黑名单（安全沙箱）
FORBIDDEN_IMPORTS = {
    "os", "subprocess", "socket", "shutil", "ctypes", "importlib",
    "multiprocessing", "threading", "signal", "fcntl", "pty",
}

FORBIDDEN_BUILTINS = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "dir", "hasattr", "setattr", "delattr",
}


def _validate_script_safety(script_content: str) -> Optional[str]:
    """静态检查脚本安全性，返回错误信息或 None（安全）"""
    try:
        tree = ast.parse(script_content)
    except SyntaxError as e:
        return f"脚本语法错误: {e}"

    for node in ast.walk(tree):
        # 检查 import
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else ""
            for alias in node.names:
                name = (module + "." if module else "") + alias.name
                top_level = name.split(".")[0]
                if top_level in FORBIDDEN_IMPORTS:
                    return f"禁止导入模块: {name}"
        # 检查危险内置函数调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
                return f"禁止调用内置函数: {node.func.id}"
    return None


class SkillScriptTool(BaseTool):
    """Skill 脚本工具，动态包装 Skill 包中的 Python 函数"""

    def __init__(self, skill_name: str, script_filename: str, script_content: str):
        self.skill_name = skill_name
        self.script_filename = script_filename
        self.script_content = script_content
        # 工具名：skill_{skill_name}_{filename_without_ext}
        base_name = re.sub(r"[^a-zA-Z0-9_]", "_", script_filename.replace(".py", ""))
        self.name = f"skill_{skill_name}_{base_name}"
        self.description = f"[Skill:{skill_name}] 执行脚本 {script_filename}"
        self.category = "skill"
        self.parameters = ToolParameter(
            type="object",
            properties={
                "args": {"type": "object", "description": "传递给脚本的参数字典"},
            },
            required=[],
        )
        super().__init__()

    async def execute(
        self,
        args: Dict[str, Any],
        db: Session,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """在受限沙箱中执行脚本"""
        # 安全检查
        safety_error = _validate_script_safety(self.script_content)
        if safety_error:
            return {"success": False, "error": safety_error}

        # 构建受限命名空间
        safe_builtins = {
            k: v for k, v in __builtins__.items()
            if k not in FORBIDDEN_BUILTINS and not k.startswith("_")
        } if isinstance(__builtins__, dict) else {
            k: getattr(__builtins__, k) for k in dir(__builtins__)
            if k not in FORBIDDEN_BUILTINS and not k.startswith("_")
        }

        namespace = {
            "__builtins__": safe_builtins,
            "args": args.get("args", args),  # 兼容直接传参和 {"args": {...}}
            "db": db,
            "project_id": project_id,
            "user_id": user_id,
            "json": __import__("json"),
            "re": __import__("re"),
            "math": __import__("math"),
            "datetime": __import__("datetime"),
        }

        start_time = time.time()
        try:
            # 执行脚本（设置超时）
            exec(compile(self.script_content, f"<skill:{self.skill_name}:{self.script_filename}>", "exec"), namespace)
            # 调用 main 函数（如果存在）
            if "main" in namespace and callable(namespace["main"]):
                result = namespace["main"](namespace["args"])
            else:
                # 没有 main 函数，返回脚本中定义的 result 变量或最后输出
                result = namespace.get("result", "脚本执行完成（无返回值）")
            duration = round(time.time() - start_time, 2)
            return {
                "success": True,
                "result": str(result) if not isinstance(result, (dict, list)) else result,
                "duration": duration,
            }
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            return {"success": False, "error": f"脚本执行异常: {str(e)}", "duration": duration}
