from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱是否存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(user)
    db.flush()
    log_audit(
        db, action="register", resource_type="user",
        resource_id=user.id, resource_name=user.username,
        user_id=user.id, username=user.username,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"email": user.email},
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录（OAuth2 格式）"""
    user = db.query(User).filter(User.username == form_data.username).first()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if not user or not verify_password(form_data.password, user.hashed_password):
        log_audit(
            db, action="login", resource_type="user",
            resource_name=form_data.username,
            username=form_data.username,
            ip_address=client_ip, user_agent=user_agent,
            status="failed", error_message="用户名或密码错误",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        log_audit(
            db, action="login", resource_type="user",
            resource_id=user.id, resource_name=user.username,
            user=user, ip_address=client_ip, user_agent=user_agent,
            status="failed", error_message="账号已被禁用",
        )
        db.commit()
        raise HTTPException(status_code=400, detail="账号已被禁用")

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=1440),
    )
    log_audit(
        db, action="login", resource_type="user",
        resource_id=user.id, resource_name=user.username,
        user=user, ip_address=client_ip, user_agent=user_agent,
    )
    db.commit()
    return Token(access_token=access_token, user=user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user
