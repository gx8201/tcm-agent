"""
用户认证 API

提供用户注册、登录、个人信息管理等功能
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/api/v1/auth", tags=["用户认证"])


# 请求模型
class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    email: EmailStr
    password: str
    nickname: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserUpdate(BaseModel):
    """用户信息更新请求"""
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    """密码修改请求"""
    old_password: str
    new_password: str


# 响应模型
class Token(BaseModel):
    """令牌响应"""
    access_token: str
    token_type: str
    user_id: int
    username: str
    nickname: Optional[str]


class UserInfo(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    nickname: Optional[str]
    avatar: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


@router.post("/register", response_model=Token)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    用户注册
    
    Args:
        user_data: 注册信息
        db: 数据库会话
    
    Returns:
        访问令牌和用户信息
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        nickname=user_data.nickname or user_data.username
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # 生成访问令牌
    access_token = create_access_token(data={"sub": db_user.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.id,
        "username": db_user.username,
        "nickname": db_user.nickname
    }


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    用户登录
    
    Args:
        form_data: 登录表单数据
        db: 数据库会话
    
    Returns:
        访问令牌和用户信息
    """
    # 查找用户
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证密码
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用"
        )
    
    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    db.commit()
    
    # 生成访问令牌
    access_token = create_access_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "nickname": user.nickname
    }


@router.get("/me", response_model=UserInfo)
async def get_user_info(current_user: User = Depends(get_current_user)):
    """
    获取当前用户信息
    
    Args:
        current_user: 当前认证用户
    
    Returns:
        用户信息
    """
    return current_user


@router.put("/me", response_model=UserInfo)
async def update_user_info(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新用户信息
    
    Args:
        user_data: 更新数据
        current_user: 当前认证用户
        db: 数据库会话
    
    Returns:
        更新后的用户信息
    """
    # 检查邮箱是否已被其他用户使用
    if user_data.email and user_data.email != current_user.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他用户注册"
            )
        current_user.email = user_data.email
    
    if user_data.nickname:
        current_user.nickname = user_data.nickname
    
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改密码
    
    Args:
        password_data: 密码数据
        current_user: 当前认证用户
        db: 数据库会话
    
    Returns:
        成功消息
    """
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "密码修改成功"}
