"""
Task Service
Core business logic for task management
Implements atomic task claiming with SELECT FOR UPDATE
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import (
    Task,
    TaskClaim,
    TaskProof,
    User,
    Transaction,
    TaskStatus,
    ClaimStatus,
    TransactionType,
    TaskCategory,
)
from app.repositories.base_repo import BaseRepository
import structlog

logger = structlog.get_logger(__name__)


class TaskService:
    """
    Task management service
    Handles all task-related business logic with atomic operations
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize task service
        
        Args:
            session: Async database session
        """
        self.session = session
        self.task_repo = BaseRepository(Task, session)
        self.claim_repo = BaseRepository(TaskClaim, session)
        self.user_repo = BaseRepository(User, session)
    
    async def get_available_tasks(
        self,
        user_id: int,
        category: Optional[TaskCategory] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Task]:
        """
        Get available tasks for user
        
        Args:
            user_id: Telegram user ID
            category: Optional task category filter
            limit: Maximum tasks to return
            offset: Pagination offset
            
        Returns:
            List of available Task instances
        """
        # Get user for rank check
        user = await self.user_repo.get_by_field("telegram_id", user_id)
        if not user or user.is_banned:
            return []
        
        # Build query for active tasks
        query = select(Task).where(
            and_(
                Task.status == TaskStatus.ACTIVE,
                Task.available_slots > 0,
                or_(
                    Task.start_date.is_(None),
                    Task.start_date <= datetime.utcnow(),
                ),
                or_(
                    Task.end_date.is_(None),
                    Task.end_date >= datetime.utcnow(),
                ),
            )
        )
        
        # Apply category filter
        if category:
            query = query.where(Task.category == category)
        
        # Apply rank restriction
        if user.current_rank:
            query = query.where(
                or_(
                    Task.min_rank_required.is_(None),
                    Task.min_rank_required == user.current_rank,
                )
            )
        
        # Order by priority and creation date
        query = query.order_by(Task.priority.desc(), Task.created_at.desc())
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        tasks = list(result.scalars().all())
        
        logger.info(
            f"Retrieved available tasks for user",
            user_id=user_id,
            task_count=len(tasks)
        )
        
        return tasks
    
    async def claim_task(
        self,
        telegram_id: int,
        task_id: int,
    ) -> Tuple[bool, str, Optional[TaskClaim]]:
        """
        Atomically claim a task using SELECT FOR UPDATE
        
        This method implements row-level locking to prevent race conditions.
        If 500 users click simultaneously, only first N users get the task
        where N = available_slots.
        
        Args:
            telegram_id: Telegram user ID
            task_id: Task ID to claim
            
        Returns:
            Tuple of (success, message, claim_instance)
        """
        try:
            # Start transaction
            async with self.session.begin():
                # Get user
                user = await self.user_repo.get_by_field("telegram_id", telegram_id)
                if not user:
                    return False, "❌ User not found. Please /start first.", None
                
                if user.is_banned:
                    return False, "❌ Your account is banned.", None
                
                # Check active claims limit
                active_claims = await self.session.execute(
                    select(TaskClaim).where(
                        and_(
                            TaskClaim.user_id == user.id,
                            TaskClaim.status.in_([
                                ClaimStatus.CLAIMED,
                                ClaimStatus.IN_PROGRESS,
                            ]),
                        )
                    )
                )
                if len(active_claims.scalars().all()) >= 5:  # Max 5 active claims
                    return False, "❌ You have reached the maximum active claims limit (5).", None
                
                # Check if already claimed
                existing_claim = await self.session.execute(
                    select(TaskClaim).where(
                        and_(
                            TaskClaim.task_id == task_id,
                            TaskClaim.user_id == user.id,
                            TaskClaim.status.in_([
                                ClaimStatus.CLAIMED,
                                ClaimStatus.IN_PROGRESS,
                                ClaimStatus.SUBMITTED,
                                ClaimStatus.APPROVED,
                            ]),
                        )
                    )
                )
                if existing_claim.scalar_one_or_none():
                    return False, "❌ You have already claimed this task.", None
                
                # SELECT FOR UPDATE - Row-level lock
                # This is the CRITICAL part for race condition prevention
                task_query = select(Task).where(
                    and_(
                        Task.id == task_id,
                        Task.status == TaskStatus.ACTIVE,
                        Task.available_slots > 0,
                    )
                ).with_for_update()
                
                result = await self.session.execute(task_query)
                task = result.scalar_one_or_none()
                
                if not task:
                    return False, "⚠️ This task is no longer available.", None
                
                # Create claim
                claim = TaskClaim(
                    task_id=task.id,
                    user_id=user.id,
                    status=ClaimStatus.CLAIMED,
                    reward_amount=task.reward,
                    bonus_amount=task.bonus_reward,
                    expires_at=datetime.utcnow() + timedelta(minutes=task.claim_timeout_minutes),
                    claimed_at=datetime.utcnow(),
                )
                self.session.add(claim)
                
                # Update task slots
                task.available_slots -= 1
                
                # Update user stats
                user.total_claims += 1
                user.pending_review += 1
                
                # Flush to get claim ID
                await self.session.flush()
                await self.session.refresh(claim)
                
                logger.info(
                    f"Task claimed successfully",
                    user_id=user.telegram_id,
                    task_id=task.id,
                    claim_id=claim.id,
                    remaining_slots=task.available_slots,
                )
                
                return True, f"✅ Task claimed successfully!\n⏰ Time limit: {task.claim_timeout_minutes} minutes", claim
            
        except Exception as e:
            logger.error(
                f"Task claim failed",
                error=str(e),
                user_id=telegram_id,
                task_id=task_id,
                exc_info=True
            )
            return False, "❌ Failed to claim task. Please try again.", None
    
    async def submit_proof(
        self,
        claim_id: int,
        user_id: int,
        proof_type: str,
        proof_data: Dict[str, Any],
        file_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Submit proof for claimed task
        
        Args:
            claim_id: Claim ID
            user_id: User telegram ID
            proof_type: Type of proof (image, video, document, link, text)
            proof_data: Proof content data
            file_id: Optional Telegram file ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            async with self.session.begin():
                # Get claim
                claim = await self.claim_repo.get_by_id(claim_id)
                if not claim:
                    return False, "❌ Claim not found."
                
                # Verify ownership
                user = await self.user_repo.get_by_field("telegram_id", user_id)
                if not user or claim.user_id != user.id:
                    return False, "❌ This is not your claim."
                
                # Check claim status
                if claim.status not in [ClaimStatus.CLAIMED, ClaimStatus.IN_PROGRESS]:
                    return False, "❌ Cannot submit proof for this claim."
                
                # Check if expired
                if claim.is_expired:
                    claim.status = ClaimStatus.EXPIRED
                    # Return slot
                    task = await self.task_repo.get_by_id(claim.task_id)
                    if task:
                        task.available_slots += 1
                    return False, "❌ Claim has expired. Task slot has been released."
                
                # Create proof
                proof = TaskProof(
                    claim_id=claim.id,
                    task_id=claim.task_id,
                    user_id=user.id,
                    proof_type=proof_type,
                    proof_data=proof_data,
                    file_id=file_id,
                    submitted_at=datetime.utcnow(),
                )
                self.session.add(proof)
                
                # Update claim status
                claim.status = ClaimStatus.SUBMITTED
                claim.submitted_at = datetime.utcnow()
                
                logger.info(
                    f"Proof submitted",
                    claim_id=claim.id,
                    user_id=user_id,
                    proof_type=proof_type,
                )
                
                return True, "✅ Proof submitted successfully! Please wait for review."
                
        except Exception as e:
            logger.error(
                f"Proof submission failed",
                error=str(e),
                claim_id=claim_id,
                exc_info=True
            )
            return False, "❌ Failed to submit proof. Please try again."
    
    async def review_task(
        self,
        claim_id: int,
        reviewer_id: int,
        approved: bool,
        rejection_reason: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Review and approve/reject a task submission
        
        Args:
            claim_id: Claim ID
            reviewer_id: Reviewer's telegram ID
            approved: Whether to approve or reject
            rejection_reason: Reason for rejection
            
        Returns:
            Tuple of (success, message)
        """
        try:
            async with self.session.begin():
                # Get claim with related task
                claim = await self.session.execute(
                    select(TaskClaim).where(TaskClaim.id == claim_id)
                )
                claim = claim.scalar_one_or_none()
                
                if not claim:
                    return False, "❌ Claim not found."
                
                if claim.status != ClaimStatus.SUBMITTED:
                    return False, "❌ No proof submitted for this claim."
                
                # Get reviewer
                reviewer = await self.user_repo.get_by_field("telegram_id", reviewer_id)
                if not reviewer or reviewer.role not in ["admin", "moderator", "super_admin"]:
                    return False, "❌ Unauthorized to review tasks."
                
                # Get user
                user = await self.user_repo.get_by_id(claim.user_id)
                if not user:
                    return False, "❌ User not found."
                
                if approved:
                    # Approve claim
                    claim.status = ClaimStatus.APPROVED
                    claim.reviewer_id = reviewer.id
                    claim.reviewed_at = datetime.utcnow()
                    
                    # Update user balance and stats
                    total_reward = float(claim.reward_amount) + float(claim.bonus_amount)
                    
                    # Create transaction
                    transaction = Transaction(
                        user_id=user.id,
                        type=TransactionType.TASK_REWARD,
                        amount=total_reward,
                        balance_before=float(user.available_balance),
                        balance_after=float(user.available_balance) + total_reward,
                        reference_id=str(claim.id),
                        reference_type="task_claim",
                        description=f"Task reward: {claim.task_id}",
                    )
                    self.session.add(transaction)
                    
                    # Update user
                    user.available_balance += total_reward
                    user.lifetime_earnings += total_reward
                    user.completed_tasks += 1
                    user.approved_tasks += 1
                    user.pending_review -= 1
                    user.rank_points += 10  # Points for completing task
                    
                    # Update rank
                    await self._update_user_rank(user)
                    
                    logger.info(
                        f"Task approved",
                        claim_id=claim.id,
                        user_id=user.telegram_id,
                        reward=total_reward,
                    )
                    
                    return True, f"✅ Task approved! User received {total_reward} BDT."
                    
                else:
                    # Reject claim
                    claim.status = ClaimStatus.REJECTED
                    claim.reviewer_id = reviewer.id
                    claim.reviewed_at = datetime.utcnow()
                    claim.rejection_reason = rejection_reason
                    
                    # Update user stats
                    user.rejected_tasks += 1
                    user.pending_review -= 1
                    
                    logger.info(
                        f"Task rejected",
                        claim_id=claim.id,
                        reason=rejection_reason,
                    )
                    
                    return True, f"❌ Task rejected. Reason: {rejection_reason}"
                    
        except Exception as e:
            logger.error(
                f"Task review failed",
                error=str(e),
                claim_id=claim_id,
                exc_info=True
            )
            return False, "❌ Review failed. Please try again."
    
    async def _update_user_rank(self, user: User) -> None:
        """
        Update user rank based on earnings and completed tasks
        
        Args:
            user: User instance to update
        """
        # Get all ranks ordered by requirements
        result = await self.session.execute(
            select(Rank).order_by(Rank.min_earnings.desc())
        )
        ranks = result.scalars().all()
        
        # Determine appropriate rank
        for rank in ranks:
            if (
                float(user.lifetime_earnings) >= float(rank.min_earnings)
                and user.completed_tasks >= rank.min_tasks
                and user.total_referrals >= rank.min_referrals
            ):
                user.current_rank = rank.name
                break
    
    async def release_expired_claims(self) -> int:
        """
        Release expired claims and return slots to task pool
        This is typically called by scheduler
        
        Returns:
            Number of released claims
        """
        async with self.session.begin():
            # Find expired claims
            expired_claims = await self.session.execute(
                select(TaskClaim).where(
                    and_(
                        TaskClaim.status.in_([ClaimStatus.CLAIMED, ClaimStatus.IN_PROGRESS]),
                        TaskClaim.expires_at < datetime.utcnow(),
                    )
                )
            )
            expired_claims = expired_claims.scalars().all()
            
            released_count = 0
            
            for claim in expired_claims:
                # Update claim status
                claim.status = ClaimStatus.EXPIRED
                
                # Return slot to task
                task = await self.task_repo.get_by_id(claim.task_id)
                if task:
                    task.available_slots += 1
                    released_count += 1
                
                # Update user stats
                user = await self.user_repo.get_by_id(claim.user_id)
                if user:
                    user.pending_review -= 1
            
            if released_count > 0:
                logger.info(f"Released {released_count} expired claims")
            
            return released_count
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """
        Get overall task statistics
        
        Returns:
            Dictionary with task statistics
        """
        # Total tasks
        total_tasks = await self.task_repo.count()
        
        # Active tasks
        active_tasks = await self.task_repo.count(
            filters={"status": TaskStatus.ACTIVE}
        )
        
        # Total claims
        total_claims = await self.claim_repo.count()
        
        # Approved claims
        approved_claims = await self.claim_repo.count(
            filters={"status": ClaimStatus.APPROVED}
        )
        
        # Total rewards distributed
        result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.type == TransactionType.TASK_REWARD
            )
        )
        total_rewards = result.scalar() or 0
        
        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "total_claims": total_claims,
            "approved_claims": approved_claims,
            "total_rewards_distributed": float(total_rewards),
        }
