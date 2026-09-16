"""
Swagger/OpenAPI 导入器
支持 Swagger 2.0 和 OpenAPI 3.0
"""
import json
from typing import List
from app.services.importers.base import BaseImporter, ImportedApi


class SwaggerImporter(BaseImporter):
    """Swagger/OpenAPI 导入器"""

    def parse(self, content: str, file_name: str = "") -> List[ImportedApi]:
        data = self._load_json(content)
        apis = []

        # 判断版本
        is_openapi3 = "openapi" in data
        base_path = data.get("basePath", "") if not is_openapi3 else ""

        paths = data.get("paths", {})
        for path, methods in paths.items():
            full_path = base_path + path
            for method, operation in methods.items():
                if method.lower() in ("get", "post", "put", "delete", "patch", "head", "options"):
                    api = self._parse_operation(
                        path=full_path,
                        method=method,
                        operation=operation,
                        data=data,
                        is_openapi3=is_openapi3,
                    )
                    if api:
                        apis.append(api)

        return apis

    def _parse_operation(self, path: str, method: str, operation: dict,
                         data: dict, is_openapi3: bool) -> ImportedApi:
        """解析单个操作"""
        name = operation.get("summary") or operation.get("operationId") or f"{method.upper()} {path}"
        description = operation.get("description", "")

        # 标签作为文件夹
        tags = operation.get("tags", [])
        folder = tags[0] if tags else ""

        # 参数
        query_params = []
        path_params = []
        headers = []
        body_type = "none"
        body_content = {}

        if is_openapi3:
            # OpenAPI 3.0
            for param in operation.get("parameters", []):
                param_info = self._resolve_ref(param, data) if "$ref" in param else param
                p_type = param_info.get("in", "")
                p = {
                    "key": param_info.get("name", ""),
                    "type": param_info.get("schema", {}).get("type", "string"),
                    "description": param_info.get("description", ""),
                    "required": param_info.get("required", False),
                    "enabled": True,
                }
                if p_type == "query":
                    query_params.append(p)
                elif p_type == "path":
                    path_params.append(p)
                elif p_type == "header":
                    headers.append({"key": p["key"], "value": "", "description": p["description"], "enabled": True})

            # 请求体
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                if "application/json" in content:
                    body_type = "json"
                    schema = content["application/json"].get("schema", {})
                    body_content = self._schema_to_example(schema, data)
                elif "application/x-www-form-urlencoded" in content:
                    body_type = "x-www-form-urlencoded"
                    schema = content["application/x-www-form-urlencoded"].get("schema", {})
                    body_content = self._schema_to_form_data(schema, data)
                elif "multipart/form-data" in content:
                    body_type = "form-data"
                    schema = content["multipart/form-data"].get("schema", {})
                    body_content = self._schema_to_form_data(schema, data)
        else:
            # Swagger 2.0
            for param in operation.get("parameters", []):
                param_info = self._resolve_ref(param, data) if "$ref" in param else param
                p_type = param_info.get("in", "")
                p = {
                    "key": param_info.get("name", ""),
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                    "required": param_info.get("required", False),
                    "enabled": True,
                }
                if p_type == "query":
                    query_params.append(p)
                elif p_type == "path":
                    path_params.append(p)
                elif p_type == "header":
                    headers.append({"key": p["key"], "value": "", "description": p["description"], "enabled": True})
                elif p_type == "body":
                    body_type = "json"
                    schema = param_info.get("schema", {})
                    body_content = self._schema_to_example(schema, data)
                elif p_type == "formData":
                    body_type = "form-data"
                    if not isinstance(body_content, list):
                        body_content = []
                    body_content.append({
                        "key": p["key"],
                        "value": "",
                        "type": param_info.get("type", "text"),
                        "enabled": True,
                    })

        # 响应示例
        response_examples = []
        responses = operation.get("responses", {})
        for status_code, resp in responses.items():
            resp_info = self._resolve_ref(resp, data) if "$ref" in resp else resp
            example = {
                "name": f"响应 {status_code}",
                "code": int(status_code) if status_code.isdigit() else 200,
                "status": resp_info.get("description", ""),
                "body": "",
                "headers": [],
            }
            if is_openapi3:
                content = resp_info.get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    example["body"] = json.dumps(self._schema_to_example(schema, data), ensure_ascii=False)
            else:
                schema = resp_info.get("schema", {})
                if schema:
                    example["body"] = json.dumps(self._schema_to_example(schema, data), ensure_ascii=False)
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

    def _resolve_ref(self, obj: dict, data: dict) -> dict:
        """解析 $ref 引用"""
        if "$ref" not in obj:
            return obj
        ref = obj["$ref"]
        parts = ref.lstrip("#/").split("/")
        result = data
        for part in parts:
            result = result.get(part, {})
        return result

    def _schema_to_example(self, schema: dict, data: dict, depth: int = 0) -> dict:
        """将 schema 转换为示例数据"""
        if depth > 5:
            return {}
        schema = self._resolve_ref(schema, data) if "$ref" in schema else schema

        schema_type = schema.get("type", "object")

        if schema_type == "object":
            result = {}
            properties = schema.get("properties", {})
            for key, prop in properties.items():
                prop = self._resolve_ref(prop, data) if "$ref" in prop else prop
                result[key] = self._schema_to_example(prop, data, depth + 1)
            return result
        elif schema_type == "array":
            items = schema.get("items", {})
            return [self._schema_to_example(items, data, depth + 1)]
        elif schema_type == "string":
            return schema.get("example", "string")
        elif schema_type == "integer":
            return schema.get("example", 0)
        elif schema_type == "number":
            return schema.get("example", 0.0)
        elif schema_type == "boolean":
            return schema.get("example", True)
        return {}

    def _schema_to_form_data(self, schema: dict, data: dict) -> list:
        """将 schema 转换为 form-data 列表"""
        schema = self._resolve_ref(schema, data) if "$ref" in schema else schema
        properties = schema.get("properties", {})
        result = []
        for key, prop in properties.items():
            prop = self._resolve_ref(prop, data) if "$ref" in prop else prop
            result.append({
                "key": key,
                "value": "",
                "type": "text",
                "description": prop.get("description", ""),
                "enabled": True,
            })
        return result
