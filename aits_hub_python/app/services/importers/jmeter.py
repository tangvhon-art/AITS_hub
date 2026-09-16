"""
JMeter .jmx 导入器（简化版）
"""
import json
import xml.etree.ElementTree as ET
from typing import List
from app.services.importers.base import BaseImporter, ImportedApi


class JMeterImporter(BaseImporter):
    """JMeter 导入器（简化版）"""

    def parse(self, content: str, file_name: str = "") -> List[ImportedApi]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return []

        apis = []
        # 查找所有 HTTPSamplerProxy
        for sampler in root.iter("HTTPSamplerProxy"):
            api = self._parse_sampler(sampler)
            if api:
                apis.append(api)

        return apis

    def _parse_sampler(self, sampler: ET.Element) -> ImportedApi:
        """解析单个 HTTP Sampler"""
        name = sampler.get("testname", "未命名请求")

        # 提取属性
        props = {}
        for prop in sampler.findall(".//stringProp"):
            props[prop.get("name", "")] = prop.text or ""
        for prop in sampler.findall(".//boolProp"):
            props[prop.get("name", "")] = prop.text or "false"

        method = props.get("HTTPSampler.method", "GET")
        path = props.get("HTTPSampler.path", "")
        domain = props.get("HTTPSampler.domain", "")
        protocol = props.get("HTTPSampler.protocol", "http")
        port = props.get("HTTPSampler.port", "")

        # 构建完整路径
        if domain and not path.startswith("http"):
            full_path = f"{protocol}://{domain}"
            if port:
                full_path += f":{port}"
            full_path += path if path.startswith("/") else "/" + path
            path = full_path

        # 参数
        query_params = []
        for elem in sampler.findall(".//elementProp"):
            if elem.get("name") == "HTTPsampler.Arguments":
                for arg in elem.findall(".//elementProp"):
                    arg_props = {}
                    for p in arg.findall("stringProp"):
                        arg_props[p.get("name", "")] = p.text or ""
                    if arg_props.get("Argument.name"):
                        query_params.append({
                            "key": arg_props["Argument.name"],
                            "value": arg_props.get("Argument.value", ""),
                            "description": "",
                            "enabled": True,
                        })

        path_params = self._extract_path_params(path)

        return ImportedApi(
            name=name,
            method=method,
            path=path,
            description="",
            headers=[],
            query_params=query_params,
            path_params=path_params,
            body_type="none",
            body_content={},
            response_examples=[],
            folder="",
        )
