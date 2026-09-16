"""
Mock 数据生成器 API
提供函数列表查询和预览功能
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.mock_data_generator import mock_generator

router = APIRouter(prefix="/api/mock-data", tags=["Mock数据生成器"])


@router.get("/functions")
def list_functions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有支持的 Mock 函数列表"""
    return {
        "functions": mock_generator.get_function_list(),
        "total": len(mock_generator.get_function_list()),
    }


@router.get("/preview")
def preview_mock(
    text: str = Query(..., description="包含 Mock 函数的文本"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预览 Mock 数据生成结果"""
    result = mock_generator.generate(text)
    return {
        "original": text,
        "result": result,
    }
