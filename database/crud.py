"""
CRUD operations for database models.
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from .models import Project, Video, Clip


# ==================== PROJECT CRUD ====================

def create_project(
    db: Session,
    name: str,
    description: Optional[str] = None,
    settings: Optional[dict] = None
) -> Project:
    """Create a new project."""
    project = Project(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        settings=settings
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str) -> Optional[Project]:
    """Get a project by ID."""
    return db.query(Project).filter(Project.id == project_id).first()


def get_all_projects(db: Session, skip: int = 0, limit: int = 100) -> List[Project]:
    """Get all projects with pagination."""
    return db.query(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit).all()


def update_project(
    db: Session,
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    settings: Optional[dict] = None,
    thumbnail: Optional[str] = None
) -> Optional[Project]:
    """Update a project."""
    project = get_project(db, project_id)
    if not project:
        return None
    
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    if settings is not None:
        project.settings = settings
    if thumbnail is not None:
        project.thumbnail = thumbnail
    
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str) -> bool:
    """Delete a project (cascade deletes videos and clips)."""
    project = get_project(db, project_id)
    if not project:
        return False
    
    db.delete(project)
    db.commit()
    return True


# ==================== VIDEO CRUD ====================

def create_video(
    db: Session,
    video_id: str,
    project_id: str,
    original_filename: str,
    upload_path: str,
    status: str = "processing",
    settings: Optional[dict] = None,
    main_transcript_path: Optional[str] = None
) -> Video:
    """Create a new video record."""
    video = Video(
        id=video_id,
        project_id=project_id,
        original_filename=original_filename,
        upload_path=upload_path,
        status=status,
        settings=settings,
        main_transcript_path=main_transcript_path
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def get_video(db: Session, video_id: str) -> Optional[Video]:
    """Get a video by ID."""
    return db.query(Video).filter(Video.id == video_id).first()


def get_videos_by_project(db: Session, project_id: str) -> List[Video]:
    """Get all videos for a project."""
    return db.query(Video).filter(Video.project_id == project_id).order_by(Video.created_at.desc()).all()


def get_all_videos(db: Session, skip: int = 0, limit: int = 100) -> List[Video]:
    """Get all videos with pagination."""
    return db.query(Video).order_by(Video.created_at.desc()).offset(skip).limit(limit).all()


def update_video_status(
    db: Session,
    video_id: str,
    status: str,
    error_message: Optional[str] = None
) -> Optional[Video]:
    """Update video status."""
    video = get_video(db, video_id)
    if not video:
        return None
    
    video.status = status
    if error_message:
        video.error_message = error_message
    if status == "complete":
        video.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(video)
    return video


def delete_video(db: Session, video_id: str) -> bool:
    """Delete a video (cascade deletes clips)."""
    video = get_video(db, video_id)
    if not video:
        return False
    
    db.delete(video)
    db.commit()
    return True


# ==================== CLIP CRUD ====================

def create_clip(
    db: Session,
    video_id: str,
    project_id: str,
    title: str,
    clip_path: str,
    output_path: Optional[str] = None,
    segment_tsv_path: Optional[str] = None,
    roi1: Optional[dict] = None,
    roi2: Optional[dict] = None,
    duration: Optional[float] = None
) -> Clip:
    """Create a new clip record."""
    clip = Clip(
        id=str(uuid.uuid4()),
        video_id=video_id,
        project_id=project_id,
        title=title,
        clip_path=clip_path,
        output_path=output_path,
        segment_tsv_path=segment_tsv_path,
        roi1=roi1,
        roi2=roi2,
        duration=duration
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def get_clip(db: Session, clip_id: str) -> Optional[Clip]:
    """Get a clip by ID."""
    return db.query(Clip).filter(Clip.id == clip_id).first()


def get_clips_by_video(db: Session, video_id: str) -> List[Clip]:
    """Get all clips for a video."""
    return db.query(Clip).filter(Clip.video_id == video_id).order_by(Clip.created_at).all()


def get_clips_by_project(db: Session, project_id: str) -> List[Clip]:
    """Get all clips for a project."""
    return db.query(Clip).filter(Clip.project_id == project_id).order_by(Clip.created_at.desc()).all()


def update_clip(
    db: Session,
    clip_id: str,
    output_path: Optional[str] = None,
    roi1: Optional[dict] = None,
    roi2: Optional[dict] = None
) -> Optional[Clip]:
    """Update clip information."""
    clip = get_clip(db, clip_id)
    if not clip:
        return None
    
    if output_path is not None:
        clip.output_path = output_path
    if roi1 is not None:
        clip.roi1 = roi1
    if roi2 is not None:
        clip.roi2 = roi2
    
    db.commit()
    db.refresh(clip)
    return clip


def delete_clip(db: Session, clip_id: str) -> bool:
    """Delete a clip."""
    clip = get_clip(db, clip_id)
    if not clip:
        return False
    
    db.delete(clip)
    db.commit()
    return True


# ==================== UTILITY FUNCTIONS ====================

def get_project_stats(db: Session, project_id: str) -> dict:
    """Get statistics for a project."""
    project = get_project(db, project_id)
    if not project:
        return {}
    
    videos = get_videos_by_project(db, project_id)
    clips = get_clips_by_project(db, project_id)
    
    completed_videos = sum(1 for v in videos if v.status == "complete")
    processing_videos = sum(1 for v in videos if v.status in ["processing", "pending_adjustment", "finalizing"])
    
    return {
        "total_videos": len(videos),
        "completed_videos": completed_videos,
        "processing_videos": processing_videos,
        "total_clips": len(clips),
        "total_duration": sum(c.duration for c in clips if c.duration)
    }
