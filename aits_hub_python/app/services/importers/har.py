"""
HAR (HTTP Archive) 导入器（简化版）
"""
import json
from typing import List
from app.services.importers.base import BaseImporter, ImportedApi


class HarImporter(BaseImporter):
    """HAR 导入器（简化版）"""

    def parse(self, content: str, file_name: str = "") -> List[ImportedApi]:
        data = self._load_json(content)
        apis = []

        entries = data.get("log", {}).get("entries", [])
        for entry in entries:
            request = entry.get("request", {})
            response = entry.get("response", {})

            method = request.get("method", "GET")
            url = request.get("url", "")
            name = f"{method} {url.split('?')[0]}"

            # 请求头
            headers = []
            for h in request.get("headers", []):
                headers.append({
                    "key": h.get("name", ""),
                    "value": h.get("value", ""),
                    "description": "",
                    "enabled": True,
                })

            # 查询参数
            query_params = []
            for q in request.get("queryString", []):
                query_params.append({
                    "key": q.get("name", ""),
                    "value": q.get("value", ""),
                    "description": "",
                    "enabled": True,
                })

            # 请求体
            body_type = "none"
            body_content = {}
            post_data = request.get("postData", {})
            if post_data:
                mime = post_data.get("mimeType", "")
                text = post_data.get("text", "")
                if "json" in mime:
                    body_type = "json"
                    try:
                        body_content = json.loads(text)
                    except json.JSONDecodeError:
                        body_content = {"raw": text}
                elif "form-urlencoded" in mime:
                    body_type = "x-www-form-urlencoded"
                    body_content = post_data.get("params", [])
                elif "multipart" in mime:
                    body_type = "form-data"
                    body_content = post_data.get("params", [])
                else:
                    body_type = "raw"
                    body_content = {"raw": text}

            # 响应示例
            response_examples = []
            if response:
                content_data = response.get("content", {})
                response_examples.append({
                    "name": "录制响应",
                    "code": response.get("status", 200),
                    "status": response.get("statusText", ""),
                    "body": content_data.get("text", ""),
                    "headers": response.get("headers", []),
                })

            path_params = self._extract_path_params(url)

            apis.append(ImportedApi(
                name=name,
                method=method,
                path=url,
                description="",
                headers=headers,
                query_params=query_params,
                path_params=path_params,
                body_type=body_type,
                body_content=body_content,
                response_examples=response_examples,
                folder="",
            ))

        return apis
