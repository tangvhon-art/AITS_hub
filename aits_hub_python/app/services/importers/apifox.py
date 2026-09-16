"""
Apifox 导入器（简化版）
Apifox 导出格式与 Swagger/OpenAPI 类似
"""
import json
from typing import List
from app.services.importers.base import BaseImporter, ImportedApi
from app.services.importers.swagger import SwaggerImporter


class ApifoxImporter(BaseImporter):
    """Apifox 导入器（简化版，复用 Swagger 解析）"""

    def parse(self, content: str, file_name: str = "") -> List[ImportedApi]:
        data = self._load_json(content)

        # Apifox 导出可能是 OpenAPI 格式或自定义格式
        if "openapi" in data or "swagger" in data:
            # 复用 Swagger 导入器
            return SwaggerImporter().parse(content, file_name)

        # 自定义格式尝试解析
        apis = []
        # Apifox 的 api_data 格式
        api_data = data.get("api_data", data.get("data", []))
        if isinstance(api_data, list):
            for item in api_data:
                api = self._parse_apifox_item(item)
                if api:
                    apis.append(api)

        return apis

    def _parse_apifox_item(self, item: dict) -> ImportedApi:
        """解析单个 Apifox 接口项"""
        name = item.get("name", item.get("title", "未命名接口"))
        method = item.get("method", "GET")
        path = item.get("path", "")
        description = item.get("description", "")

        # 请求参数
        query_params = []
        for p in item.get("query_params", item.get("parameters", [])):
            if p.get("in", "query") == "query":
                query_params.append({
                    "key": p.get("name", ""),
                    "value": "",
                    "description": p.get("description", ""),
                    "enabled": True,
                })

        path_params = self._extract_path_params(path)

        # 请求体
        body_type = "none"
        body_content = {}
        request_body = item.get("request_body", {})
        if request_body:
            body_type = request_body.get("type", "json")
            body_content = request_body.get("content", {})

        # 响应示例
        response_examples = []
        for resp in item.get("responses", []):
            response_examples.append({
                "name": resp.get("name", f"响应 {resp.get('code', 200)}"),
                "code": resp.get("code", 200),
                "status": "",
                "body": resp.get("body", ""),
                "headers": [],
            })

        return ImportedApi(
            name=name,
            method=method,
            path=path,
            description=description,
            headers=[],
            query_params=query_params,
            path_params=path_params,
            body_type=body_type,
            body_content=body_content,
            response_examples=response_examples,
            folder=item.get("folder", ""),
        )
