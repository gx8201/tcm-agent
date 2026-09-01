"""
对话模型

定义对话和消息表结构，支持用户隔离
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Conversation(Base):
    """对话表"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联消息
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, conversation_id='{self.conversation_id}')>"


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user 或 assistant
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    steps = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联对话
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}')>"
