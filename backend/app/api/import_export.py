"""
数据导入导出 API
支持 Excel 格式的测试用例导入导出
"""
import json
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.models.test_case import TestCase
from app.models.requirement import TestRequirement

try:
    from openpyxl import Workbook, load_workbook
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

router = APIRouter()
project_router = APIRouter(prefix="/api/projects/{project_id}/data")


# Excel 列定义
CASE_COLUMNS = [
    ("用例标题", "title", 30),
    ("所属模块", "module", 20),
    ("优先级", "priority", 10),
    ("用例类型", "case_type", 15),
    ("前置条件", "preconditions", 30),
    ("测试步骤", "steps", 50),
    ("预期结果", "expected_result", 40),
    ("状态", "status", 10),
    ("关联需求ID", "req_id", 15),
    ("BDD内容", "bdd_content", 40),
]


@project_router.get("/cases/export")
def export_cases(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导出测试用例为 Excel"""
    if not HAS_OPENPYXL:
        raise HTTPException(status_code=500, detail="openpyxl 未安装，请运行 pip install openpyxl")

    cases = db.query(TestCase).filter(TestCase.project_id == project_id).order_by(TestCase.module, TestCase.priority).all()

    log_audit(
        db, action="export", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "count": len(cases), "format": "excel"},
    )
    db.commit()

    wb = Workbook()
    ws = wb.active
    ws.title = "测试用例"

    # 写入表头
    for col_idx, (header, _, width) in enumerate(CASE_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = cell.font.copy(bold=True)
        ws.column_dimensions[cell.column_letter].width = width

    # 写入数据
    for row_idx, case in enumerate(cases, 2):
        for col_idx, (_, field, _) in enumerate(CASE_COLUMNS, 1):
            value = getattr(case, field, "")
            if field == "steps" and isinstance(value, str):
                try:
                    steps_list = json.loads(value)
                    value = "\n".join([f"{i+1}. {s}" for i, s in enumerate(steps_list)])
                except (json.JSONDecodeError, TypeError):
                    pass
            ws.cell(row=row_idx, column=col_idx, value=value or "")

    # 生成文件
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"test_cases_{project_id}_{china_now_naive().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@project_router.post("/cases/import")
async def import_cases(
    project_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从 Excel 导入测试用例"""
    if not HAS_OPENPYXL:
        raise HTTPException(status_code=500, detail="openpyxl 未安装，请运行 pip install openpyxl")

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 Excel 文件格式 (.xlsx, .xls)")

    content = await file.read()
    try:
        wb = load_workbook(BytesIO(content))
        ws = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 文件解析失败: {str(e)}")

    # 读取表头，建立列映射
    headers = {}
    for col in range(1, ws.max_column + 1):
        header_value = ws.cell(row=1, column=col).value
        if header_value:
            headers[str(header_value).strip()] = col

    # 字段映射
    field_map = {}
    for header_name, field_name, _ in CASE_COLUMNS:
        if header_name in headers:
            field_map[field_name] = headers[header_name]

    if "title" not in field_map:
        raise HTTPException(status_code=400, detail="Excel 必须包含「用例标题」列")

    # 读取数据行
    imported = 0
    failed = 0
    errors = []

    for row in range(2, ws.max_row + 1):
        try:
            title = ws.cell(row=row, column=field_map.get("title", 0)).value
            if not title:
                continue

            case_data = {
                "project_id": project_id,
                "title": str(title).strip(),
                "created_by": current_user.id,
            }

            for field_name, col_idx in field_map.items():
                if field_name == "title":
                    continue
                value = ws.cell(row=row, column=col_idx).value
                if value is not None and value != "":
                    if field_name == "steps":
                        # 尝试解析步骤
                        steps_text = str(value)
                        steps = []
                        for line in steps_text.split("\n"):
                            line = line.strip()
                            if line:
                                # 移除序号前缀
                                import re
                                line = re.sub(r'^\d+[\.\、]\s*', '', line)
                                steps.append(line)
                        case_data["steps"] = json.dumps(steps, ensure_ascii=False) if steps else json.dumps([steps_text], ensure_ascii=False)
                    elif field_name == "req_id":
                        try:
                            case_data["req_id"] = int(value)
                        except (ValueError, TypeError):
                            pass
                    else:
                        case_data[field_name] = str(value).strip()

            # 设置默认值
            case_data.setdefault("module", "默认模块")
            case_data.setdefault("priority", "P2")
            case_data.setdefault("case_type", "functional")
            case_data.setdefault("status", "active")
            case_data.setdefault("preconditions", "")
            case_data.setdefault("expected_result", "")
            case_data.setdefault("steps", json.dumps(["执行测试"], ensure_ascii=False))

            case = TestCase(**case_data)
            db.add(case)
            imported += 1

        except Exception as e:
            failed += 1
            errors.append(f"第 {row} 行: {str(e)}")

    log_audit(
        db, action="import", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "filename": file.filename, "imported": imported, "failed": failed},
        status="success" if failed == 0 else "partial",
    )
    db.commit()

    return {
        "detail": "导入完成",
        "imported": imported,
        "failed": failed,
        "errors": errors[:10]  # 最多返回前10个错误
    }


@project_router.get("/cases/template")
def download_template(project_id: int, current_user: User = Depends(get_current_user)):
    """下载用例导入模板"""
    if not HAS_OPENPYXL:
        raise HTTPException(status_code=500, detail="openpyxl 未安装，请运行 pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = "测试用例模板"

    # 写入表头
    for col_idx, (header, _, width) in enumerate(CASE_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = cell.font.copy(bold=True)
        ws.column_dimensions[cell.column_letter].width = width

    # 写入示例数据
    example = {
        "title": "用户登录成功",
        "module": "用户管理",
        "priority": "P0",
        "case_type": "functional",
        "preconditions": "用户已注册",
        "steps": "1. 打开登录页\n2. 输入用户名密码\n3. 点击登录",
        "expected_result": "登录成功，跳转到首页",
        "status": "active",
        "req_id": "",
        "bdd_content": "",
    }
    for col_idx, (_, field, _) in enumerate(CASE_COLUMNS, 1):
        ws.cell(row=2, column=col_idx, value=example.get(field, ""))

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=test_case_template.xlsx"}
    )
