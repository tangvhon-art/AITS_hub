"""Skill API — CRUD + 匹配测试 + 执行 + Zip 导入导出"""
import hashlib
import io
import json
import logging
import os
import zipfile
from typing import Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.skill import Skill
from app.schemas.skill import (
    SkillCreate, SkillUpdate, SkillResponse, SkillListResponse,
    SkillMatchRequest, SkillMatchResponse, SkillExecuteRequest, SkillImportResult,
)
from app.core.deps import get_current_user
from app.core.timezone import china_now_naive
from app.agents.skill_engine import skill_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["Skill"])

SKILL_STATIC_DIR = "static/skills"


# ==================== CRUD ====================

@router.get("", response_model=SkillListResponse)
def list_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    source: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Skill).filter(Skill.is_deleted == False)
    if category:
        query = query.filter(Skill.category == category)
    if source:
        query = query.filter(Skill.source == source)
    if is_active is not None:
        query = query.filter(Skill.is_active == is_active)
    total = query.count()
    items = query.order_by(Skill.sort_order.asc(), Skill.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": items}


@router.post("", response_model=SkillResponse)
def create_skill(data: SkillCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if db.query(Skill).filter(Skill.name == data.name, Skill.is_deleted == False).first():
        raise HTTPException(400, f"Skill 名称已存在: {data.name}")
    skill = Skill(
        name=data.name, title=data.title, description=data.description, category=data.category,
        version=data.version, author=data.author, source="manual",
        trigger_config=data.trigger_config, skill_config=data.skill_config,
        is_active=data.is_active, sort_order=data.sort_order, created_by=current_user.id,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    skill_engine.invalidate_cache()
    return skill


@router.put("/{skill_id}", response_model=SkillResponse)
def update_skill(skill_id: int, data: SkillUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.is_deleted == False).first()
    if not skill:
        raise HTTPException(404, "Skill 不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    skill_engine.invalidate_cache()
    return skill


@router.delete("/{skill_id}")
def delete_skill(skill_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.is_deleted == False).first()
    if not skill:
        raise HTTPException(404, "Skill 不存在")
    if skill.is_builtin:
        raise HTTPException(400, "内置 Skill 不可删除，可禁用")
    skill.is_deleted = True
    skill.deleted_at = china_now_naive()
    db.commit()
    skill_engine.invalidate_cache()
    return {"message": "删除成功"}


@router.post("/{skill_id}/toggle", response_model=SkillResponse)
def toggle_skill(skill_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.is_deleted == False).first()
    if not skill:
        raise HTTPException(404, "Skill 不存在")
    skill.is_active = not skill.is_active
    db.commit()
    db.refresh(skill)
    skill_engine.invalidate_cache()
    return skill


# ==================== 匹配与执行 ====================

@router.post("/match", response_model=SkillMatchResponse)
def match_skill(data: SkillMatchRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    skill = skill_engine.match(data.message, data.project_id, db)
    if skill:
        return {"matched": True, "skill": skill, "reason": f"命中触发条件: {skill.trigger_config}"}
    return {"matched": False, "skill": None, "reason": "未匹配到任何 Skill"}


@router.post("/{skill_id}/execute")
async def execute_skill(skill_id: int, data: SkillExecuteRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.is_deleted == False).first()
    if not skill:
        raise HTTPException(404, "Skill 不存在")
    from fastapi.responses import StreamingResponse
    async def event_generator():
        async for event in skill_engine.execute(skill, data.message, db, data.project_id, data.user_id or current_user.id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==================== Zip 导入导出 ====================

@router.post("/import", response_model=SkillImportResult)
async def import_skill(file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    导入 Skill zip 包（业界标准 skill.md 格式）

    包结构：
      skill.md          — 主文件，YAML frontmatter + Markdown 正文（正文即 System Prompt）
      prompts/          — 可选，额外提示词文件
      scripts/          — 可选，Python 脚本
      icon.png/icon.jpg — 可选，图标
    """
    warnings = []
    try:
        content = await file.read()
        if len(content) > 2 * 1024 * 1024:
            return {"success": False, "name": "", "title": "", "version": "", "warnings": [], "message": "包大小超过 2MB 限制"}
        package_hash = hashlib.sha256(content).hexdigest()

        existing = db.query(Skill).filter(Skill.package_hash == package_hash, Skill.is_deleted == False).first()
        if existing:
            warnings.append(f"该包已导入过（id={existing.id}），将更新内容")

        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            # 查找 skill.md：支持根目录或子文件夹（第一层为 skill 名称文件夹）
            md_file = next((n for n in names if n.lower().endswith("skill.md") and not n.startswith("__MACOSX")), None)
            if not md_file:
                if any(n.lower().endswith("skill.yaml") for n in names):
                    warnings.append("检测到旧格式 skill.yaml，建议迁移为 skill.md")
                    return _import_legacy_yaml(content, package_hash, db, current_user, warnings)
                return {"success": False, "name": "", "title": "", "version": "", "warnings": [],
                        "message": "包内缺少 skill.md（需包含 YAML frontmatter + Markdown 正文）"}
            raw_md = zf.read(md_file).decode("utf-8")
            # 确定基础目录（skill.md 所在文件夹），用于解析 prompts/ scripts/ icon
            base_dir = os.path.dirname(md_file)
            if base_dir:
                base_dir += "/"
            warnings.append(f"检测到包结构: 基础目录='{base_dir or '根目录'}'")

        config, system_prompt = _parse_skill_md(raw_md)
        name = config.get("name", "")
        title = config.get("title", "") or name  # title 可选，缺省用 name
        description = config.get("description", "")
        if not name:
            return {"success": False, "name": name, "title": title, "version": config.get("version", ""),
                    "warnings": [], "message": "skill.md frontmatter 缺少必填字段 name"}
        if not title:
            title = name

        # 不排除软删除记录：唯一约束在 name 字段上，软删除的同名记录也会阻止插入
        existing_name = db.query(Skill).filter(Skill.name == name).first()
        if existing_name:
            if existing_name.is_builtin:
                return {"success": False, "name": name, "title": title, "version": config.get("version", ""),
                        "warnings": [], "message": "不能覆盖内置 Skill"}
            skill = existing_name
            # 如果之前被软删除，恢复它
            if skill.is_deleted:
                skill.is_deleted = False
                skill.deleted_at = None
                warnings.append("已恢复之前删除的同名 Skill")
            skill.source = "imported"
            skill.version = config.get("version", "1.0.0")
            skill.author = config.get("author", "")
            skill.category = config.get("category", "other")
            skill.description = config.get("description", "")
            skill.package_hash = package_hash
            skill.raw_yaml = raw_md
            warnings.append(f"已覆盖同名 Skill（id={existing_name.id}）")
        else:
            skill = Skill(
                name=name, title=title, description=config.get("description", ""),
                category=config.get("category", "other"), version=config.get("version", "1.0.0"),
                author=config.get("author", ""), source="imported", package_hash=package_hash,
                raw_yaml=raw_md, created_by=current_user.id,
            )
            db.add(skill)

        skill.trigger_config = config.get("trigger", {})
        prompts_data = {}
        scripts_data = {}
        files_data = {}  # 完整文件树 {相对路径: 内容}
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for n in zf.namelist():
                # 跳过 __MACOSX、隐藏文件和目录
                if n.startswith("__MACOSX") or n.startswith(".") or n.endswith("/"):
                    continue
                rel_path = n[len(base_dir):] if base_dir and n.startswith(base_dir) else n
                if not rel_path:
                    continue
                # 读取文件内容（文本文件）
                try:
                    raw = zf.read(n)
                    # 二进制文件（图片等）只记录元信息，不存内容
                    if rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.pdf', '.zip')):
                        files_data[rel_path] = f"[二进制文件, {len(raw)} bytes]"
                        continue
                    text_content = raw.decode("utf-8")
                except (UnicodeDecodeError, Exception):
                    files_data[rel_path] = f"[二进制文件, {len(raw)} bytes]"
                    continue

                # 存入完整文件树（限制单文件 64KB）
                if len(text_content) <= 64 * 1024:
                    files_data[rel_path] = text_content
                else:
                    files_data[rel_path] = text_content[:64 * 1024] + "\n... [文件过大已截断]"
                    warnings.append(f"文件 {rel_path} 超过 64KB，已截断存储")

                # 兼容旧字段：prompts/ 和 scripts/
                if rel_path.startswith("prompts/") and rel_path.endswith((".md", ".txt")):
                    prompts_data[os.path.basename(rel_path)] = text_content
                elif rel_path.startswith("scripts/") and rel_path.endswith(".py"):
                    if len(text_content) <= 32 * 1024:
                        scripts_data[os.path.basename(rel_path)] = text_content
                    else:
                        warnings.append(f"脚本 {os.path.basename(rel_path)} 超过 32KB，已跳过")
                elif rel_path in ("icon.png", "icon.jpg"):
                    os.makedirs(SKILL_STATIC_DIR, exist_ok=True)
                    icon_path = f"{SKILL_STATIC_DIR}/{skill.id or 'new'}_{rel_path}"
                    with open(icon_path, "wb") as f:
                        f.write(raw)
                    skill.icon_path = icon_path

        skill.files = files_data
        skill.prompts = prompts_data
        skill.scripts = scripts_data
        if files_data:
            warnings.append(f"已导入 {len(files_data)} 个文件")
        if scripts_data:
            warnings.append("脚本需审核后才能执行")

        cfg = config.get("config", {})
        cfg["system_prompt"] = system_prompt
        allowed = cfg.get("allowed_tools", [])
        valid_tools = [t.name for t in __import__("app.agents.tools.registry", fromlist=["tool_registry"]).tool_registry.list_tools()]
        valid_allowed = [t for t in allowed if t in valid_tools]
        invalid = [t for t in allowed if t not in valid_tools]
        if invalid:
            warnings.append(f"未知工具已移除: {', '.join(invalid)}")
        cfg["allowed_tools"] = valid_allowed
        skill.skill_config = cfg

        db.commit()
        db.refresh(skill)
        skill_engine.invalidate_cache()
        return {"id": skill.id, "name": skill.name, "title": skill.title, "version": skill.version,
                "source": "imported", "warnings": warnings, "success": True, "message": "导入成功"}

    except Exception as e:
        logger.error(f"Skill 导入失败: {e}", exc_info=True)
        return {"success": False, "name": "", "title": "", "version": "", "warnings": [], "message": f"导入失败: {e}"}


def _parse_skill_md(raw_md: str) -> tuple[dict, str]:
    """解析 skill.md：提取 YAML frontmatter 和 Markdown 正文"""
    config = {}
    body = raw_md
    if raw_md.startswith("---"):
        end_idx = raw_md.find("\n---", 3)
        if end_idx != -1:
            fm_text = raw_md[3:end_idx].strip()
            body = raw_md[end_idx + 4:].strip()
            try:
                config = yaml.safe_load(fm_text) or {}
            except Exception:
                # yaml 解析失败（如特殊字符），降级为手动逐行解析
                config = _parse_frontmatter_manual(fm_text)
    return config, body


def _parse_frontmatter_manual(fm_text: str) -> dict:
    """手动解析 frontmatter（兜底方案），支持 key: value 和 key: "value" 格式"""
    import re
    result = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^(\w+)\s*:\s*(.*)$', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            # 去除首尾引号
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            result[key] = val
    return result


def _import_legacy_yaml(content: bytes, package_hash: str, db: Session, current_user, warnings: list):
    """兼容旧版 skill.yaml 格式"""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        raw_yaml = zf.read("skill.yaml").decode("utf-8")
        config = yaml.safe_load(raw_yaml)
    name = config.get("name", "")
    title = config.get("title", "") or name
    if not name:
        return {"success": False, "name": name, "title": title, "version": config.get("version", ""),
                "warnings": warnings, "message": "skill.yaml 缺少必填字段 name"}
    if not title:
        title = name
    existing_name = db.query(Skill).filter(Skill.name == name).first()
    if existing_name:
        if existing_name.is_builtin:
            return {"success": False, "name": name, "title": title, "version": config.get("version", ""),
                    "warnings": warnings, "message": "不能覆盖内置 Skill"}
        skill = existing_name
        if skill.is_deleted:
            skill.is_deleted = False
            skill.deleted_at = None
            warnings.append("已恢复之前删除的同名 Skill")
        skill.source = "imported"
        skill.version = config.get("version", "1.0.0")
        skill.author = config.get("author", "")
        skill.category = config.get("category", "other")
        skill.description = config.get("description", "")
        skill.package_hash = package_hash
        skill.raw_yaml = raw_yaml
        warnings.append(f"已覆盖同名 Skill（id={existing_name.id}）")
    else:
        skill = Skill(
            name=name, title=title, description=config.get("description", ""),
            category=config.get("category", "other"), version=config.get("version", "1.0.0"),
            author=config.get("author", ""), source="imported", package_hash=package_hash,
            raw_yaml=raw_yaml, created_by=current_user.id,
        )
        db.add(skill)
    skill.trigger_config = config.get("trigger", {})
    cfg = config.get("config", {})
    cfg["system_prompt"] = cfg.get("system_prompt", "")
    allowed = cfg.get("allowed_tools", [])
    valid_tools = [t.name for t in __import__("app.agents.tools.registry", fromlist=["tool_registry"]).tool_registry.list_tools()]
    cfg["allowed_tools"] = [t for t in allowed if t in valid_tools]
    skill.skill_config = cfg
    db.commit()
    db.refresh(skill)
    skill_engine.invalidate_cache()
    return {"id": skill.id, "name": skill.name, "title": skill.title, "version": skill.version,
            "source": "imported", "warnings": warnings, "success": True, "message": "导入成功（旧格式兼容）"}


@router.post("/import-text")
async def import_skill_text(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """从 skill.md 文本内容导入（无需 zip 包）"""
    raw_md = body.get("content", "")
    if not raw_md or not raw_md.strip():
        return {"success": False, "name": "", "title": "", "version": "", "warnings": [], "message": "内容不能为空"}

    warnings = []
    package_hash = hashlib.sha256(raw_md.encode("utf-8")).hexdigest()

    existing = db.query(Skill).filter(Skill.package_hash == package_hash, Skill.is_deleted == False).first()
    if existing:
        return {"success": False, "name": existing.name, "title": existing.title, "version": existing.version,
                "warnings": [], "message": f"该内容已导入过（id={existing.id}）"}

    config, system_prompt = _parse_skill_md(raw_md)
    name = config.get("name", "")
    title = config.get("title", "") or name
    if not name:
        return {"success": False, "name": name, "title": title, "version": config.get("version", ""),
                "warnings": [], "message": "skill.md frontmatter 缺少必填字段 name"}
    if not title:
        title = name

    existing_name = db.query(Skill).filter(Skill.name == name, Skill.is_deleted == False).first()
    if existing_name:
        if existing_name.is_builtin:
            return {"success": False, "name": name, "title": title, "version": config.get("version", ""),
                    "warnings": [], "message": "不能覆盖内置 Skill"}
        skill = existing_name
        skill.source = "manual"
        skill.version = config.get("version", "1.0.0")
        skill.author = config.get("author", "")
        skill.category = config.get("category", "other")
        skill.description = config.get("description", "")
        skill.package_hash = package_hash
        skill.raw_yaml = raw_md
        warnings.append(f"已覆盖同名 Skill（id={existing_name.id}）")
    else:
        skill = Skill(
            name=name, title=title, description=config.get("description", ""),
            category=config.get("category", "other"), version=config.get("version", "1.0.0"),
            author=config.get("author", ""), source="manual", package_hash=package_hash,
            raw_yaml=raw_md, created_by=current_user.id,
        )
        db.add(skill)

    skill.trigger_config = config.get("trigger", {})
    cfg = config.get("config", {})
    cfg["system_prompt"] = system_prompt
    allowed = cfg.get("allowed_tools", [])
    valid_tools = [t.name for t in __import__("app.agents.tools.registry", fromlist=["tool_registry"]).tool_registry.list_tools()]
    cfg["allowed_tools"] = [t for t in allowed if t in valid_tools]
    skill.skill_config = cfg

    db.commit()
    db.refresh(skill)
    skill_engine.invalidate_cache()
    return {"id": skill.id, "name": skill.name, "title": skill.title, "version": skill.version,
            "source": "manual", "warnings": warnings, "success": True, "message": "导入成功"}


@router.get("/{skill_id}/export")
def export_skill(skill_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """导出 Skill 为 zip 包"""
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.is_deleted == False).first()
    if not skill:
        raise HTTPException(404, "Skill 不存在")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 优先使用 files 字段（完整文件树），兼容旧数据用 prompts/scripts
        if skill.files:
            # 导出完整文件树（保持原始目录结构）
            for fpath, content in skill.files.items():
                if content.startswith("[二进制文件"):
                    continue  # 跳过二进制文件占位
                zf.writestr(fpath, content)
        else:
            # 兼容旧数据：生成 skill.md + prompts/ + scripts/
            cfg = skill.skill_config or {}
            system_prompt = cfg.get("system_prompt", "")
            fm = {
                "name": skill.name, "title": skill.title, "description": skill.description or "",
                "version": skill.version or "1.0.0", "author": skill.author or "",
                "category": skill.category or "other",
                "trigger": skill.trigger_config or {},
                "config": {k: v for k, v in cfg.items() if k != "system_prompt"},
            }
            md_content = f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---\n\n{system_prompt}\n"
            zf.writestr("skill.md", md_content)
            if skill.prompts:
                for fname, content in skill.prompts.items():
                    zf.writestr(f"prompts/{fname}", content)
            if skill.scripts:
                for fname, content in skill.scripts.items():
                    zf.writestr(f"scripts/{fname}", content)
        # icon
        if skill.icon_path and os.path.exists(skill.icon_path):
            with open(skill.icon_path, "rb") as f:
                zf.writestr(os.path.basename(skill.icon_path), f.read())

    buf.seek(0)
    filename = f"{skill.name}-v{skill.version or '1.0.0'}.zip"
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
