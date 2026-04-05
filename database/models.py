"""
SQLAlchemy models for ViralCutter project management.
"""
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Float, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


class Project(Base):
    """
    Project model - groups related videos and clips together.
    """
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    thumbnail = Column(String, nullable=True)  # Path to thumbnail image
    settings = Column(JSON, nullable=True)  # Default settings for the project
    
    # Relationships with cascade delete
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "thumbnail": self.thumbnail,
            "settings": self.settings,
            "video_count": len(self.videos) if self.videos else 0,
            "clip_count": len(self.clips) if self.clips else 0
        }


class Video(Base):
    """
    Video model - represents an uploaded video being processed.
    """
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True)  # job_id
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String, nullable=False)
    upload_path = Column(String, nullable=False)
    status = Column(String, nullable=False)  # processing, pending_adjustment, finalizing, complete, error
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    settings = Column(JSON, nullable=True)  # Processing settings used
    main_transcript_path = Column(String, nullable=True)  # Path to main TSV transcript
    error_message = Column(String, nullable=True)  # Error details if status is 'error'
    
    # Relationships
    project = relationship("Project", back_populates="videos")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Video(id={self.id}, filename={self.original_filename}, status={self.status})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "original_filename": self.original_filename,
            "upload_path": self.upload_path,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "settings": self.settings,
            "main_transcript_path": self.main_transcript_path,
            "error_message": self.error_message,
            "clip_count": len(self.clips) if self.clips else 0
        }


class Clip(Base):
    """
    Clip model - represents a processed video clip/segment.
    """
    __tablename__ = "clips"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    clip_path = Column(String, nullable=False)  # Path to temporary clip
    output_path = Column(String, nullable=True)  # Path to final processed clip
    segment_tsv_path = Column(String, nullable=True)  # Path to segment transcript
    roi1 = Column(JSON, nullable=True)  # Region of interest 1 {x, y, w, h}
    roi2 = Column(JSON, nullable=True)  # Region of interest 2 {x, y, w, h}
    duration = Column(Float, nullable=True)  # Duration in seconds
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    video = relationship("Video", back_populates="clips")
    project = relationship("Project", back_populates="clips")
    
    def __repr__(self):
        return f"<Clip(id={self.id}, title={self.title})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "video_id": self.video_id,
            "project_id": self.project_id,
            "title": self.title,
            "clip_path": self.clip_path,
            "output_path": self.output_path,
            "segment_tsv_path": self.segment_tsv_path,
            "roi1": self.roi1,
            "roi2": self.roi2,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
