from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from auth.database import get_async_session
from auth.models import User
from auth.config import current_active_user, current_superuser
from models import FeedbackCreate, FeedbackRead
from sqlalchemy import text
import uuid

feedback_router = APIRouter(tags=["feedback"])

@feedback_router.post("/feedback", response_model=dict)
async def submit_feedback(
    feedback: FeedbackCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Submit feedback for a session"""
    try:
        await session.execute(text("""
            INSERT INTO feedbacks (user_id, session_id, content)
            VALUES (:user_id, :session_id, :content)
        """), {
            "user_id": user.id,
            "session_id": feedback.session_id,
            "content": feedback.content
        })
        await session.commit()
        return {"message": "Feedback submitted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )

@feedback_router.get("/admin/feedbacks", response_model=List[FeedbackRead])
async def list_feedbacks(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(current_superuser),
    session: AsyncSession = Depends(get_async_session)
):
    """List all feedbacks (admin only)"""
    try:
        result = await session.execute(text("""
            SELECT f.id, f.user_id, f.session_id, f.content, f.created_at, u.username
            FROM feedbacks f
            JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
            OFFSET :skip LIMIT :limit
        """), {"skip": skip, "limit": limit})
        
        feedbacks = []
        for row in result:
            feedbacks.append(FeedbackRead(
                id=row.id,
                user_id=row.user_id,
                session_id=row.session_id,
                content=row.content,
                created_at=row.created_at.isoformat(),
                username=row.username
            ))
            
        return feedbacks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list feedbacks: {str(e)}"
        )

@feedback_router.get("/admin/feedbacks/{feedback_id}", response_model=FeedbackRead)
async def get_feedback(
    feedback_id: uuid.UUID,
    user: User = Depends(current_superuser),
    session: AsyncSession = Depends(get_async_session)
):
    """Get specific feedback details (admin only)"""
    try:
        result = await session.execute(text("""
            SELECT f.id, f.user_id, f.session_id, f.content, f.created_at, u.username
            FROM feedbacks f
            JOIN users u ON f.user_id = u.id
            WHERE f.id = :feedback_id
        """), {"feedback_id": feedback_id})
        
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
            
        return FeedbackRead(
            id=row.id,
            user_id=row.user_id,
            session_id=row.session_id,
            content=row.content,
            created_at=row.created_at.isoformat(),
            username=row.username
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback: {str(e)}"
        )
