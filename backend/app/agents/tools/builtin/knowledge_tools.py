"""知识库相关工具"""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.agents.tools.base import BaseTool, ToolParameter


class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge"
    description = "在项目知识库中检索相关文档和内容"
    category = "knowledge"
    parameters = ToolParameter(properties={
        "query": {"type": "string", "description": "检索查询内容"},
        "top_k": {"type": "integer", "description": "返回结果数量，默认5，最大10"},
    }, required=["query"])

    async def execute(self, args: Dict[str, Any], db: Session, project_id: Optional[int] = None, user_id: Optional[int] = None) -> Any:
        from app.services.knowledge_base import knowledge_base_service
        if not project_id:
            return {"error": "未指定项目"}
        query = args.get("query", "")
        top_k = min(args.get("top_k", 5), 10)
        if not query:
            return {"error": "查询内容不能为空"}
        try:
            results = knowledge_base_service.search(db=db, project_id=project_id, query=query, top_k=top_k)
        except Exception as e:
            return {"error": f"知识库检索失败: {str(e)}"}
        return {
            "query": query,
            "total": len(results) if isinstance(results, list) else 0,
            "results": [
                {"title": r.get("title", ""), "content": r.get("content", r.get("text", ""))[:300], "score": r.get("score", r.get("similarity"))}
                for r in (results if isinstance(results, list) else [])
            ],
        }
