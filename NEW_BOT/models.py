from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Habit(Base):
    __tablename__ = 'habits'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    time = Column(Time, nullable=False)
    enabled = Column(Boolean, default=True)
    completed_count = Column(Integer, default=0)
    last_completed = Column(DateTime)

class UserSettings(Base):
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    notifications_enabled = Column(Boolean, default=True)
    timezone = Column(String, default="Europe/Moscow")