"""
UI 自动化自愈模型
- UIPageVisit: 页面访问原始记录（只追加）
- UIPageProfile: 页面画像（聚合知识）
- UIElementFingerprint: 元素指纹库
- UIHealingRecord: 自愈记录
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON, BigInteger, Index
from app.database import Base
from app.core.timezone import china_now_naive


class UIPageVisit(Base):
    """页面访问原始记录（只追加，不修改）"""
    __tablename__ = "ui_page_visit"
    __table_args__ = (
        Index("idx_page_visit_project_page", "project_id", "page_identifier"),
        Index("idx_page_visit_script_run", "script_id", "run_id"),
        Index("idx_page_visit_result", "action_result"),
        {"comment": "UI自动化页面访问原始记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, nullable=False, index=True, comment="项目ID")
    script_id = Column(Integer, nullable=True, comment="脚本ID")
    run_id = Column(Integer, nullable=True, comment="执行记录ID")
    step_index = Column(Integer, nullable=True, comment="步骤序号")
    page_url = Column(String(500), default="", comment="页面URL")
    page_title = Column(String(200), default="", comment="页面标题")
    page_identifier = Column(String(200), default="", comment="页面标识（URL路径归一化）")
    action_type = Column(String(30), default="", comment="操作类型: click/fill/select/assert/navigate/wait")
    target_selector = Column(Text, default="", comment="原定位器")
    target_text = Column(String(500), default="", comment="目标元素文本")
    action_result = Column(String(20), default="success", comment="结果: success/fail/timeout/healed")
    fail_reason = Column(Text, default="", comment="失败原因")
    dom_snapshot = Column(Text, default="", comment="页面DOM树快照（精简）")
    screenshot_path = Column(String(500), default="", comment="截图存储路径")
    elements_json = Column(JSON, comment="关键元素列表")
    source = Column(String(20), default="execution", comment="来源: execution/exploration")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class UIPageProfile(Base):
    """页面画像（聚合后的页面知识）"""
    __tablename__ = "ui_page_profile"
    __table_args__ = (
        Index("uk_page_profile", "project_id", "page_identifier", unique=True),
        {"comment": "UI自动化页面画像表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, nullable=False, index=True, comment="项目ID")
    page_identifier = Column(String(200), nullable=False, comment="页面唯一标识")
    page_name = Column(String(200), default="", comment="AI推断的页面业务名称")
    page_description = Column(Text, default="", comment="AI生成的页面功能描述")
    key_elements = Column(JSON, comment="关键元素列表")
    success_paths = Column(JSON, comment="历史成功操作路径")
    failure_patterns = Column(JSON, comment="常见失败模式")
    reachable_from = Column(JSON, comment="可达页面列表")
    visit_count = Column(Integer, default=0, comment="累计访问次数")
    success_rate = Column(Float, default=1.0, comment="操作成功率")
    last_aggregated_at = Column(DateTime, nullable=True, comment="最后聚合时间")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class UIElementFingerprint(Base):
    """元素指纹库（多维度特征，用于定位失败时匹配备选）"""
    __tablename__ = "ui_element_fingerprint"
    __table_args__ = (
        Index("idx_elem_fp_page", "project_id", "page_identifier"),
        Index("idx_elem_fp_text", "project_id", "page_identifier", "element_text"),
        {"comment": "UI自动化元素指纹库表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, nullable=False, index=True, comment="项目ID")
    page_identifier = Column(String(200), default="", comment="所属页面标识")
    element_role = Column(String(50), default="", comment="元素角色: button/input/link/...")
    element_text = Column(String(500), default="", comment="可见文本")
    selectors = Column(JSON, comment="所有可用定位器 [{type,value,confidence,last_used_at}]")
    attributes = Column(JSON, comment="关键属性 {id,name,aria-label,placeholder,data-testid,...}")
    parent_chain = Column(String(500), default="", comment="父元素链")
    visual_hash = Column(String(64), default="", comment="视觉特征哈希")
    occurrence_count = Column(Integer, default=1, comment="出现次数")
    success_count = Column(Integer, default=0, comment="成功操作次数")
    fail_count = Column(Integer, default=0, comment="失败次数")
    last_seen_at = Column(DateTime, default=china_now_naive, comment="最后出现时间")
    is_stable = Column(Boolean, default=False, comment="是否稳定元素（出现率>90%）")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class UIHealingRecord(Base):
    """自愈记录（每次自愈的完整记录，可审计可回滚）"""
    __tablename__ = "ui_healing_record"
    __table_args__ = (
        Index("idx_healing_script", "script_id"),
        Index("idx_healing_run", "run_id"),
        Index("idx_healing_result", "healing_result"),
        {"comment": "UI自动化自愈记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, nullable=False, index=True, comment="项目ID")
    script_id = Column(Integer, nullable=True, comment="脚本ID")
    run_id = Column(Integer, nullable=True, comment="执行记录ID")
    step_index = Column(Integer, nullable=True, comment="失败步骤")
    page_url = Column(String(500), default="", comment="页面URL")
    page_identifier = Column(String(200), default="", comment="页面标识")
    original_selector = Column(Text, default="", comment="原定位器")
    action_type = Column(String(30), default="click", comment="操作类型")
    fail_reason = Column(String(200), default="", comment="失败原因")
    healing_level = Column(String(10), default="L1", comment="自愈等级: L1/L2/L3/L4")
    healing_strategy = Column(String(50), default="", comment="采用的策略")
    suggested_selector = Column(Text, default="", comment="修复后的定位器")
    ai_reasoning = Column(Text, default="", comment="AI推理过程")
    candidates = Column(JSON, comment="AI候选定位器列表")
    healing_result = Column(String(20), default="pending", comment="结果: success/fail/pending/pending_review")
    screenshot_before = Column(String(500), default="", comment="失败时截图")
    screenshot_after = Column(String(500), default="", comment="修复后截图")
    applied_to_script = Column(Boolean, default=False, comment="是否已回写到脚本")
    confirmed_by = Column(Integer, nullable=True, comment="人工确认人ID")
    confirmed_at = Column(DateTime, nullable=True, comment="确认时间")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
