"""
HTTP 客户端 - 基于 httpx
支持所有 HTTP 方法、form-data、x-www-form-urlencoded、raw、binary、文件上传
"""
import json
import time
import httpx
from typing import Optional, Dict, Any, List, Tuple


class HttpResponse:
    """HTTP 响应封装"""

    def __init__(self, status_code: int, headers: Dict[str, str], body: str,
                 elapsed_ms: float, size: int, error: Optional[str] = None):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.elapsed_ms = elapsed_ms
        self.size = size
        self.error = error

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except Exception:
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "elapsed_ms": self.elapsed_ms,
            "size": self.size,
            "error": self.error,
        }


class HttpClient:
    """HTTP 客户端"""

    def __init__(self, timeout: int = 30, verify_ssl: bool = False, follow_redirects: bool = True):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.follow_redirects = follow_redirects

    def _build_headers(self, headers_list: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
        """将 [{key, value, enabled}] 格式转为 dict"""
        result = {}
        if not headers_list:
            return result
        for h in headers_list:
            if h.get("enabled", True) and h.get("key"):
                result[h["key"]] = str(h.get("value", ""))
        return result

    def _build_params(self, params_list: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
        """将 [{key, value, enabled}] 格式转为 dict"""
        result = {}
        if not params_list:
            return result
        for p in params_list:
            if p.get("enabled", True) and p.get("key"):
                result[p["key"]] = str(p.get("value", ""))
        return result

    def _build_body(self, body_type: str, body_content: Any) -> Tuple[Optional[Any], Optional[Dict[str, str]], Optional[str]]:
        """
        构建请求体
        返回 (content, files, data, json_body) 中的合适组合
        """
        if body_type == "none" or body_content is None:
            return None, None, None, None

        if body_type == "raw":
            if isinstance(body_content, dict):
                body_str = HttpClient.serialize_body(body_type, body_content)
                return body_str.encode("utf-8"), None, None, None
            return str(body_content), None, None, None

        if body_type == "json":
            body_str = HttpClient.serialize_body(body_type, body_content)
            if body_str:
                return body_str.encode("utf-8"), None, None, None
            return None, None, None, None

        if body_type == "x-www-form-urlencoded":
            data = {}
            if isinstance(body_content, list):
                for item in body_content:
                    if item.get("enabled", True) and item.get("key"):
                        data[item["key"]] = str(item.get("value", ""))
            elif isinstance(body_content, dict):
                data = {k: str(v) for k, v in body_content.items()}
            return None, None, data, None

        if body_type == "form-data":
            data = {}
            files = {}
            if isinstance(body_content, list):
                for item in body_content:
                    if not item.get("enabled", True) or not item.get("key"):
                        continue
                    if item.get("type") == "file":
                        # 文件上传，value 为文件路径或 base64
                        file_path = item.get("value", "")
                        try:
                            with open(file_path, "rb") as f:
                                files[item["key"]] = (item.get("filename", file_path.split("/")[-1]), f.read())
                        except Exception:
                            data[item["key"]] = str(item.get("value", ""))
                    else:
                        data[item["key"]] = str(item.get("value", ""))
            return None, files, data, None

        if body_type == "binary":
            if isinstance(body_content, str) and body_content.startswith("file://"):
                file_path = body_content[7:]
                try:
                    with open(file_path, "rb") as f:
                        return f.read(), None, None, None
                except Exception:
                    return body_content.encode(), None, None, None
            if isinstance(body_content, str):
                return body_content.encode(), None, None, None
            return body_content, None, None, None

        return None, None, None, None

    @staticmethod
    def serialize_body(body_type: str, body_content: Any) -> str:
        """将 body 序列化为 httpx 实际发送的字符串（供脚本计算 MD5 用）"""
        if body_type == "none" or body_content is None:
            return ""
        if body_type in ("json", "raw"):
            if isinstance(body_content, str):
                if body_type == "json":
                    try:
                        return json.dumps(json.loads(body_content), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                    except Exception:
                        pass
                return body_content
            if isinstance(body_content, (dict, list)):
                if body_type == "json":
                    return json.dumps(body_content, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                return json.dumps(body_content, ensure_ascii=False, separators=(",", ":"))
            return str(body_content)
        return str(body_content) if body_content else ""

    def send(self, method: str, url: str,
             headers: Optional[List[Dict[str, Any]]] = None,
             params: Optional[List[Dict[str, Any]]] = None,
             body_type: str = "none",
             body_content: Any = None,
             timeout: Optional[int] = None) -> HttpResponse:
        """发送 HTTP 请求（同步）"""
        start = time.time()
        try:
            req_headers = self._build_headers(headers)
            req_params = self._build_params(params)
            content, files, data, json_body = self._build_body(body_type, body_content)

            # json body 和 raw(dict) body 现在通过 content 发送（而非 json_body），需确保 Content-Type 存在
            if content is not None and (body_type == "json" or (body_type == "raw" and isinstance(content, bytes))):
                if not any(k.lower() == "content-type" for k in req_headers):
                    req_headers["Content-Type"] = "application/json"

            with httpx.Client(
                timeout=timeout or self.timeout,
                verify=self.verify_ssl,
                follow_redirects=self.follow_redirects,
            ) as client:
                resp = client.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    params=req_params,
                    content=content,
                    files=files,
                    data=data,
                    json=json_body,
                )
                elapsed = (time.time() - start) * 1000
                body_text = resp.text
                return HttpResponse(
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    body=body_text,
                    elapsed_ms=round(elapsed, 2),
                    size=len(resp.content),
                )
        except httpx.TimeoutException as e:
            elapsed = (time.time() - start) * 1000
            return HttpResponse(0, {}, "", round(elapsed, 2), 0, error=f"请求超时: {e}")
        except httpx.ConnectError as e:
            elapsed = (time.time() - start) * 1000
            return HttpResponse(0, {}, "", round(elapsed, 2), 0, error=f"连接失败: {e}")
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HttpResponse(0, {}, "", round(elapsed, 2), 0, error=f"请求异常: {e}")

    async def asend(self, method: str, url: str,
                    headers: Optional[List[Dict[str, Any]]] = None,
                    params: Optional[List[Dict[str, Any]]] = None,
                    body_type: str = "none",
                    body_content: Any = None,
                    timeout: Optional[int] = None) -> HttpResponse:
        """发送 HTTP 请求（异步）"""
        start = time.time()
        try:
            req_headers = self._build_headers(headers)
            req_params = self._build_params(params)
            content, files, data, json_body = self._build_body(body_type, body_content)

            # json body 和 raw(dict) body 现在通过 content 发送（而非 json_body），需确保 Content-Type 存在
            if content is not None and (body_type == "json" or (body_type == "raw" and isinstance(content, bytes))):
                if not any(k.lower() == "content-type" for k in req_headers):
                    req_headers["Content-Type"] = "application/json"

            async with httpx.AsyncClient(
                timeout=timeout or self.timeout,
                verify=self.verify_ssl,
                follow_redirects=self.follow_redirects,
            ) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    params=req_params,
                    content=content,
                    files=files,
                    data=data,
                    json=json_body,
                )
                elapsed = (time.time() - start) * 1000
                body_text = resp.text
                return HttpResponse(
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    body=body_text,
                    elapsed_ms=round(elapsed, 2),
                    size=len(resp.content),
                )
        except httpx.TimeoutException as e:
            elapsed = (time.time() - start) * 1000
            return HttpResponse(0, {}, "", round(elapsed, 2), 0, error=f"请求超时: {e}")
        except httpx.ConnectError as e:
            elapsed = (time.time() - start) * 1000
            return HttpResponse(0, {}, "", round(elapsed, 2), 0, error=f"连接失败: {e}")
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HttpResponse(0, {}, "", round(elapsed, 2), 0, error=f"请求异常: {e}")
