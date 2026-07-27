"""
Complete Database Models
All SQLAlchemy models with relationships, indexes, and constraints
"""

from datetime import datetime, timedelta
from typing import Optional, List
import enum
import uuid

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Index,
    CheckConstraint,
    UniqueConstraint,
    DECIMAL,
    func,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.session import Base


# ==================== ENUMS ====================

class UserRole(str, enum.Enum):
    USER = "user"
    PREMIUM = "premium"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class TaskStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"


class TaskCategory(str, enum.Enum):
    VIDEO = "video"
    APP_INSTALL = "app_install"
    TELEGRAM_JOIN = "telegram_join"
    WEBSITE_VISIT = "website_visit"
    SURVEY = "survey"
    SOCIAL_MEDIA = "social_media"
    CUSTOM = "custom"


class ClaimStatus(str, enum.Enum):
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TASK_REWARD = "task_reward"
    REFERRAL_COMMISSION = "referral_commission"
    BONUS = "bonus"
    ADJUSTMENT = "adjustment"
    PROMO = "promo"


class WithdrawalStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WithdrawalMethod(str, enum.Enum):
    BKASH = "bkash"
    NAGAD = "nagad"
    ROCKET = "rocket"
    BINANCE_PAY = "binance_pay"
    USDT = "usdt"


class RankName(str, enum.Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    ELITE = "elite"


class SupportTicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ==================== MODELS ====================

class User(Base):
    """
    User model - Core user profile and wallet
    """
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True, unique=True)
    
    # Role and Status
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    is_muted = Column(Boolean, default=False, nullable=False)
    
    # Balance
    available_balance = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    pending_balance = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    lifetime_earnings = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    referral_earnings = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    total_withdrawn = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    
    # Statistics
    completed_tasks = Column(Integer, default=0, nullable=False)
    approved_tasks = Column(Integer, default=0, nullable=False)
    rejected_tasks = Column(Integer, default=0, nullable=False)
    pending_review = Column(Integer, default=0, nullable=False)
    total_claims = Column(Integer, default=0, nullable=False)
    
    # Referral System
    referral_code = Column(String(20), unique=True, nullable=False, index=True)
    referred_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    total_referrals = Column(Integer, default=0, nullable=False)
    active_referrals = Column(Integer, default=0, nullable=False)
    
    # Ranking
    current_rank = Column(Enum(RankName), default=RankName.BRONZE, nullable=False)
    rank_points = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tasks_created = relationship("Task", back_populates="creator", foreign_keys="Task.creator_id")
    claims = relationship("TaskClaim", back_populates="user", foreign_keys="TaskClaim.user_id")
    transactions = relationship("Transaction", back_populates="user", foreign_keys="Transaction.user_id")
    withdrawals = relationship("Withdrawal", back_populates="user", foreign_keys="Withdrawal.user_id")
    
    __table_args__ = (
        Index("idx_user_telegram", "telegram_id"),
        Index("idx_user_referral", "referral_code"),
        CheckConstraint("available_balance >= 0", name="ck_balance_non_negative"),
        CheckConstraint("pending_balance >= 0", name="ck_pending_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Task(Base):
    """
    Task model - Micro tasks available for users
    """
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(Enum(TaskCategory), nullable=False, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.ACTIVE, nullable=False, index=True)
    
    # Reward Configuration
    reward = Column(DECIMAL(10, 2), nullable=False)
    bonus_reward = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    
    # Task Requirements
    requirements = Column(JSON, nullable=True)
    tutorial_text = Column(Text, nullable=True)
    tutorial_video_url = Column(String(500), nullable=True)
    estimated_time_minutes = Column(Integer, default=5, nullable=False)
    difficulty_level = Column(Integer, default=1, nullable=False)  # 1-5 scale
    
    # Proof Configuration
    proof_types = Column(JSON, nullable=False, default=list)  # ["image", "video", "document", "link", "text"]
    proof_required_count = Column(Integer, default=1, nullable=False)
    
    # Slot Management
    total_slots = Column(Integer, nullable=False, default=0)
    available_slots = Column(Integer, nullable=False, default=0)
    max_claims_per_user = Column(Integer, default=1, nullable=False)
    
    # Timing
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    claim_timeout_minutes = Column(Integer, default=30, nullable=False)
    
    # Creator and Approval
    creator_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    auto_approve = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    tags = Column(JSON, default=list, nullable=True)
    priority = Column(Integer, default=0, nullable=False)  # Higher = more priority
    min_rank_required = Column(Enum(RankName), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    creator = relationship("User", back_populates="tasks_created", foreign_keys=[creator_id])
    claims = relationship("TaskClaim", back_populates="task", foreign_keys="TaskClaim.task_id")
    proofs = relationship("TaskProof", back_populates="task", foreign_keys="TaskProof.task_id")
    
    __table_args__ = (
        Index("idx_task_status_category", "status", "category"),
        Index("idx_task_available", "available_slots"),
        CheckConstraint("reward > 0", name="ck_reward_positive"),
        CheckConstraint("available_slots >= 0", name="ck_slots_non_negative"),
        CheckConstraint("available_slots <= total_slots", name="ck_slots_valid"),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, reward={self.reward})>"


class TaskClaim(Base):
    """
    Task Claim - Atomic task claiming with locking
    Implements SELECT FOR UPDATE for race condition prevention
    """
    __tablename__ = "task_claims"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    # Status Management
    status = Column(Enum(ClaimStatus), default=ClaimStatus.CLAIMED, nullable=False, index=True)
    
    # Timing
    claimed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Review Information
    reviewer_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Reward Tracking
    reward_amount = Column(DECIMAL(10, 2), nullable=False)
    bonus_amount = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    
    # Optimistic Locking
    lock_version = Column(Integer, default=1, nullable=False)
    
    # Relationships
    task = relationship("Task", back_populates="claims", foreign_keys=[task_id])
    user = relationship("User", back_populates="claims", foreign_keys=[user_id])
    proofs = relationship("TaskProof", back_populates="claim", foreign_keys="TaskProof.claim_id")
    
    __table_args__ = (
        Index("idx_claim_task_user", "task_id", "user_id"),
        Index("idx_claim_expires", "expires_at"),
        UniqueConstraint("task_id", "user_id", name="uq_one_active_claim_per_task"),
        CheckConstraint("reward_amount >= 0", name="ck_claim_reward_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<TaskClaim(id={self.id}, task={self.task_id}, user={self.user_id}, status={self.status})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if claim has expired"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def time_remaining(self) -> timedelta:
        """Get remaining time before expiration"""
        remaining = self.expires_at - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


class TaskProof(Base):
    """
    Task Proof - Evidence submission for completed tasks
    """
    __tablename__ = "task_proofs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    claim_id = Column(BigInteger, ForeignKey("task_claims.id"), nullable=False, index=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    # Proof Content
    proof_type = Column(String(50), nullable=False)  # image, video, document, link, text
    proof_data = Column(JSON, nullable=False)
    file_id = Column(String(500), nullable=True)  # Telegram file ID for media
    file_path = Column(String(500), nullable=True)  # Local storage path
    
    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Timestamps
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    claim = relationship("TaskClaim", back_populates="proofs", foreign_keys=[claim_id])
    task = relationship("Task", back_populates="proofs", foreign_keys=[task_id])
    
    __table_args__ = (
        Index("idx_proof_claim", "claim_id"),
        Index("idx_proof_task_user", "task_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TaskProof(id={self.id}, claim={self.claim_id}, type={self.proof_type})>"


class Transaction(Base):
    """
    Transaction - Complete wallet transaction ledger
    """
    __tablename__ = "transactions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    # Transaction Details
    type = Column(Enum(TransactionType), nullable=False, index=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    balance_before = Column(DECIMAL(15, 2), nullable=False)
    balance_after = Column(DECIMAL(15, 2), nullable=False)
    
    # Reference Information
    reference_id = Column(String(100), nullable=True)
    reference_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default="completed", nullable=False)
    
    # Metadata
    metadata = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="transactions", foreign_keys=[user_id])
    
    __table_args__ = (
        Index("idx_transaction_user_date", "user_id", "created_at"),
        Index("idx_transaction_type_date", "type", "created_at"),
        CheckConstraint("amount != 0", name="ck_amount_not_zero"),
    )

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, user={self.user_id}, type={self.type}, amount={self.amount})>"


class Withdrawal(Base):
    """
    Withdrawal - User withdrawal requests
    """
    __tablename__ = "withdrawals"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    # Amount Details
    amount = Column(DECIMAL(15, 2), nullable=False)
    fee = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    net_amount = Column(DECIMAL(15, 2), nullable=False)
    
    # Payment Method
    method = Column(Enum(WithdrawalMethod), nullable=False)
    account_number = Column(String(100), nullable=False)
    account_name = Column(String(100), nullable=True)
    
    # Status
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False, index=True)
    
    # Processing Information
    processed_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    transaction_reference = Column(String(100), nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Security
    otp_verified = Column(Boolean, default=False, nullable=False)
    otp_code = Column(String(10), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="withdrawals", foreign_keys=[user_id])
    
    __table_args__ = (
        Index("idx_withdrawal_user_status", "user_id", "status"),
        Index("idx_withdrawal_date", "created_at"),
        CheckConstraint("amount > 0", name="ck_withdrawal_amount_positive"),
        CheckConstraint("net_amount >= 0", name="ck_net_amount_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Withdrawal(id={self.id}, user={self.user_id}, amount={self.amount}, status={self.status})>"


class PromoCode(Base):
    """
    PromoCode - Promotional codes for rewards
    """
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    
    # Value Configuration
    type = Column(String(20), nullable=False)  # fixed, percentage
    value = Column(DECIMAL(10, 2), nullable=False)
    max_uses = Column(Integer, nullable=True)
    current_uses = Column(Integer, default=0, nullable=False)
    max_per_user = Column(Integer, default=1, nullable=False)
    
    # Restrictions
    min_balance_required = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    max_payout = Column(DECIMAL(10, 2), nullable=True)
    
    # Validity
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Creator
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint("value > 0", name="ck_promo_value_positive"),
        CheckConstraint("current_uses >= 0", name="ck_uses_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<PromoCode(code={self.code}, value={self.value}, uses={self.current_uses})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if promo code has expired"""
        if self.end_date and datetime.utcnow() > self.end_date:
            return True
        if self.max_uses and self.current_uses >= self.max_uses:
            return True
        return False


class Referral(Base):
    """
    Referral - Referral tracking system
    """
    __tablename__ = "referrals"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    referred_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Referral Level
    level = Column(Integer, default=1, nullable=False)  # 1=direct, 2=indirect, etc.
    
    # Earnings Tracking
    total_earned = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_referral_referrer", "referrer_id"),
        Index("idx_referral_referred", "referred_id"),
        UniqueConstraint("referrer_id", "referred_id", name="uq_referral_pair"),
    )

    def __repr__(self) -> str:
        return f"<Referral(referrer={self.referrer_id}, referred={self.referred_id})>"


class Rank(Base):
    """
    Rank - Ranking system configuration
    """
    __tablename__ = "ranks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Enum(RankName), unique=True, nullable=False)
    
    # Requirements
    min_earnings = Column(DECIMAL(15, 2), nullable=False)
    min_tasks = Column(Integer, nullable=False)
    min_referrals = Column(Integer, default=0, nullable=False)
    
    # Benefits
    bonus_percentage = Column(Float, default=0.0, nullable=False)
    withdrawal_fee_discount = Column(Float, default=0.0, nullable=False)
    priority_support = Column(Boolean, default=False, nullable=False)
    
    # Visual
    icon = Column(String(10), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint("min_earnings >= 0", name="ck_min_earnings_non_negative"),
        CheckConstraint("min_tasks >= 0", name="ck_min_tasks_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Rank(name={self.name}, min_earnings={self.min_earnings})>"


class Setting(Base):
    """
    Setting - Global application configuration
    """
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(20), default="string", nullable=False)
    description = Column(Text, nullable=True)
    
    # Audit
    updated_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_setting_key", "key"),
    )

    def __repr__(self) -> str:
        return f"<Setting(key={self.key}, value={self.value[:20]})>"


class SupportTicket(Base):
    """
    SupportTicket - Customer support system
    """
    __tablename__ = "support_tickets"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    
    # Content
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)
    priority = Column(Integer, default=1, nullable=False)  # 1-5
    
    # Status
    status = Column(Enum(SupportTicketStatus), default=SupportTicketStatus.OPEN, nullable=False, index=True)
    
    # Assignment
    assigned_to = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_ticket_user_status", "user_id", "status"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_priority_valid"),
    )

    def __repr__(self) -> str:
        return f"<SupportTicket(id={self.id}, user={self.user_id}, status={self.status})>"


class Announcement(Base):
    """
    Announcement - Broadcast messages to users
    """
    __tablename__ = "announcements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), default="text", nullable=False)  # text, photo, video, document
    
    # Media
    file_id = Column(String(500), nullable=True)
    media_group = Column(JSON, nullable=True)
    
    # Targeting
    target_roles = Column(JSON, nullable=True)
    target_users = Column(JSON, nullable=True)
    
    # Delivery Status
    is_sent = Column(Boolean, default=False, nullable=False)
    sent_count = Column(Integer, default=0, nullable=False)
    scheduled_for = Column(DateTime, nullable=True)
    
    # Creator
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_announcement_status", "is_sent"),
    )

    def __repr__(self) -> str:
        return f"<Announcement(id={self.id}, title={self.title}, sent={self.is_sent})>"


class AuditLog(Base):
    """
    AuditLog - Security and activity audit trail
    """
    __tablename__ = "audit_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    
    # Action Details
    action = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # create, update, delete, login, etc.
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(100), nullable=True)
    
    # Change Tracking
    details = Column(JSON, default=dict, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Context
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Result
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_date", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user={self.user_id})>"