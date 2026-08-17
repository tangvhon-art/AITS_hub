"""
接口导入 API
五种格式导入 + 预览
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.api_test import ApiDefinition, ApiModule
from app.schemas.api_test import ApiImportRequest, ApiImportPreviewResponse
from app.services.importers import get_importer, get_supported_formats
from app.services.notification_service import notify_event

router = APIRouter(prefix="/api/projects/{project_id}/api-import", tags=["接口测试-导入"])

@router.get("/formats")
def list_import_formats(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取支持的导入格式"""
    get_project(project_id, db, current_user)
    return {"formats": get_supported_formats()}

@router.post("/preview", response_model=ApiImportPreviewResponse)
async def preview_import(
    project_id: int,
    import_type: str = Form(...),
    file: UploadFile = File(...),
    module_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入预览"""
    get_project(project_id, db, current_user)

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="ignore")

    importer = get_importer(import_type)
    if not importer:
        raise HTTPException(status_code=400, detail=f"不支持的导入格式: {import_type}")

    imported_apis = importer.parse(text, file.filename or "")

    return ApiImportPreviewResponse(
        import_type=import_type,
        file_name=file.filename or "",
        total_count=len(imported_apis),
        apis=[api.to_dict() for api in imported_apis],
    )

@router.post("")
async def import_apis(
    project_id: int,
    import_type: str = Form(...),
    file: UploadFile = File(...),
    module_id: Optional[int] = Form(None),
    selected_indices: Optional[str] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入接口"""
    get_project(project_id, db, current_user)

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="ignore")

    importer = get_importer(import_type)
    if not importer:
        raise HTTPException(status_code=400, detail=f"不支持的导入格式: {import_type}")

    imported_apis = importer.parse(text, file.filename or "")

    # 选择要导入的索引
    if selected_indices:
        try:
            indices = json.loads(selected_indices)
            imported_apis = [imported_apis[i] for i in indices if 0 <= i < len(imported_apis)]
        except (json.JSONDecodeError, IndexError):
            pass

    # 处理目录
    target_module_id = module_id
    folder_module_map = {}

    imported_count = 0
    for api in imported_apis:
        # 按文件夹创建目录
        if api.folder and api.folder not in folder_module_map:
            folder = ApiModule(
                project_id=project_id,
                parent_id=target_module_id,
                name=api.folder,
                sort_order=db.query(ApiModule).filter(
                    ApiModule.project_id == project_id,
                    ApiModule.parent_id == target_module_id,
                ).count(),
                created_by=current_user.id,
            )
            db.add(folder)
            db.flush()
            folder_module_map[api.folder] = folder.id

        api_module_id = folder_module_map.get(api.folder, target_module_id)

        # 创建接口定义
        definition = ApiDefinition(
            project_id=project_id,
            module_id=api_module_id,
            name=api.name,
            method=api.method,
            path=api.path,
            description=api.description,
            headers=api.headers,
            query_params=api.query_params,
            path_params=api.path_params,
            body_type=api.body_type,
            body_content=api.body_content,
            response_examples=api.response_examples,
            status="active",
            created_by=current_user.id,
        )
        db.add(definition)
        imported_count += 1

    log_audit(
        db, action="import", resource_type="project",
        resource_id=project_id, resource_name="接口导入",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "import_type": import_type, "imported_count": imported_count},
    )
    db.commit()

    # 发送接口导入完成通知
    try:
        notify_event(
            project_id,
            "api.import.completed",
            {
                "file_name": file.filename or "导入文件",
                "import_type": import_type,
                "created_count": imported_count,
                "updated_count": 0,
                "failed_count": max(0, len(imported_apis) - imported_count),
                "errors": [],
            },
            triggered_by=current_user.id,
        )
    except Exception as notify_e:
        import logging
        logging.getLogger(__name__).warning(f"发送接口导入通知失败: {notify_e}")

    return {"success": True, "imported_count": imported_count, "total": len(imported_apis)}
