"""
接口导入解析器
支持 Postman, Swagger/OpenAPI, JMeter, HAR, Apifox
"""
from app.services.importers.base import BaseImporter
from app.services.importers.postman import PostmanImporter
from app.services.importers.swagger import SwaggerImporter
from app.services.importers.jmeter import JMeterImporter
from app.services.importers.har import HarImporter
from app.services.importers.apifox import ApifoxImporter

IMPORTERS = {
    "postman": PostmanImporter,
    "swagger": SwaggerImporter,
    "openapi": SwaggerImporter,
    "jmeter": JMeterImporter,
    "har": HarImporter,
    "apifox": ApifoxImporter,
}


def get_importer(import_type: str) -> BaseImporter:
    """获取导入器"""
    importer_class = IMPORTERS.get(import_type.lower())
    if not importer_class:
        raise ValueError(f"不支持的导入类型: {import_type}")
    return importer_class()


def get_supported_formats() -> list:
    """获取支持的导入格式列表"""
    return list(IMPORTERS.keys())


__all__ = [
    "BaseImporter",
    "PostmanImporter",
    "SwaggerImporter",
    "JMeterImporter",
    "HarImporter",
    "ApifoxImporter",
    "get_importer",
    "get_supported_formats",
]
