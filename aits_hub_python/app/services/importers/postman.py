"""
Postman Collection 导入器
支持 v2.0 和 v2.1 格式
"""
import json
from typing import List
from app.services.importers.base import BaseImporter, ImportedApi


class PostmanImporter(BaseImporter):
    """Postman Collection 导入器"""

    def parse(self, content: str, file_name: str = "") -> List[ImportedApi]:
        data = self._load_json(content)
        apis = []
        self._parse_collection(data, apis, folder="")
        return apis

    def _parse_collection(self, data: dict, apis: List[ImportedApi], folder: str = ""):
        """递归解析 Postman Collection"""
        items = data.get("item", [])
        for item in items:
            if "item" in item:
                # 文件夹
                folder_name = item.get("name", "")
                new_folder = f"{folder}/{folder_name}" if folder else folder_name
                self._parse_collection(item, apis, new_folder)
            else:
                # 请求
                api = self._parse_request(item, folder)
                if api:
                    apis.append(api)

    def _parse_request(self, item: dict, folder: str) -> ImportedApi:
        """解析单个请求"""
        request = item.get("request", {})
        if not request:
            return None

        name = item.get("name", "未命名请求")
        method = request.get("method", "GET")

        # URL
        url_data = request.get("url", {})
        if isinstance(url_data, str):
            path = url_data
        else:
            path = url_data.get("raw", "")
            # 去掉 host 部分，保留路径
            path_parts = url_data.get("path", [])
            if path_parts:
                path = "/" + "/".join(path_parts)

        # 描述
        description = ""
        if isinstance(request.get("description"), str):
            description = request["description"]
        elif isinstance(request.get("description"), dict):
            description = request["description"].get("content", "")

        # 请求头
        headers = []
        for h in request.get("header", []):
            if isinstance(h, dict):
                headers.append({
                    "key": h.get("key", ""),
                    "value": h.get("value", ""),
                    "description": h.get("description", ""),
                    "enabled": not h.get("disabled", False),
                })

        # 查询参数
        query_params = []
        if isinstance(url_data, dict):
            for q in url_data.get("query", []):
                query_params.append({
                    "key": q.get("key", ""),
                    "value": q.get("value", ""),
                    "description": q.get("description", ""),
                    "enabled": not q.get("disabled", False),
                })

        # 请求体
        body_type = "none"
        body_content = {}
        body = request.get("body", {})
        if body:
            mode = body.get("mode", "none")
            if mode == "raw":
                body_type = "raw"
                raw_content = body.get("raw", "")
                try:
                    body_content = json.loads(raw_content)
                    body_type = "json"
                except json.JSONDecodeError:
                    body_content = {"raw": raw_content}
            elif mode == "formdata":
                body_type = "form-data"
                body_content = body.get("formdata", [])
            elif mode == "urlencoded":
                body_type = "x-www-form-urlencoded"
                body_content = body.get("urlencoded", [])

        # 路径参数
        path_params = self._extract_path_params(path)

        # 响应示例
        response_examples = []
        for resp in item.get("response", []):
            example = {
                "name": resp.get("name", ""),
                "status": resp.get("status", ""),
                "code": resp.get("code", 200),
                "body": resp.get("body", ""),
                "headers": resp.get("header", []),
            }
            response_examples.append(example)

        return ImportedApi(
            name=name,
            method=method,
            path=path,
            description=description,
            headers=headers,
            query_params=query_params,
            path_params=path_params,
            body_type=body_type,
            body_content=body_content,
            response_examples=response_examples,
            folder=folder,
        )
