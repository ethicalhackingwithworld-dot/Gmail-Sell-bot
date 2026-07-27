"""
Base Repository
Generic repository pattern for database operations
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.session import Base
import structlog

logger = structlog.get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with common CRUD operations
    Implements Repository Pattern for data access abstraction
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository
        
        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session
    
    async def get_by_id(
        self,
        id: Any,
        options: Optional[List] = None
    ) -> Optional[ModelType]:
        """
        Get record by primary key
        
        Args:
            id: Primary key value
            options: List of eager loading options
            
        Returns:
            Model instance or None
        """
        query = select(self.model).where(self.model.id == id)
        
        if options:
            for option in options:
                query = query.options(option)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_field(
        self,
        field: str,
        value: Any,
        options: Optional[List] = None
    ) -> Optional[ModelType]:
        """
        Get record by specific field
        
        Args:
            field: Field name to filter
            value: Field value
            options: Eager loading options
            
        Returns:
            Model instance or None
        """
        if not hasattr(self.model, field):
            raise AttributeError(f"Model {self.model.__name__} has no field '{field}'")
        
        query = select(self.model).where(getattr(self.model, field) == value)
        
        if options:
            for option in options:
                query = query.options(option)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[ModelType]:
        """
        Get multiple records with optional filtering and pagination
        
        Args:
            filters: Dictionary of field:value pairs
            order_by: Field name to order by (add '-' for DESC)
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of model instances
        """
        query = select(self.model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)
        
        # Apply ordering
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by))
        
        # Apply pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, **kwargs) -> ModelType:
        """
        Create new record
        
        Args:
            **kwargs: Model field values
            
        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        
        logger.info(
            f"Created {self.model.__name__}",
            model=self.model.__name__,
            id=instance.id
        )
        return instance
    
    async def update(
        self,
        id: Any,
        **kwargs
    ) -> Optional[ModelType]:
        """
        Update record by ID
        
        Args:
            id: Primary key value
            **kwargs: Fields to update
            
        Returns:
            Updated model instance or None
        """
        instance = await self.get_by_id(id)
        if not instance:
            return None
        
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        await self.session.flush()
        await self.session.refresh(instance)
        
        logger.info(
            f"Updated {self.model.__name__}",
            model=self.model.__name__,
            id=id,
            updated_fields=list(kwargs.keys())
        )
        return instance
    
    async def delete(self, id: Any) -> bool:
        """
        Delete record by ID
        
        Args:
            id: Primary key value
            
        Returns:
            True if deleted, False if not found
        """
        instance = await self.get_by_id(id)
        if not instance:
            return False
        
        await self.session.delete(instance)
        await self.session.flush()
        
        logger.info(
            f"Deleted {self.model.__name__}",
            model=self.model.__name__,
            id=id
        )
        return True
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filtering
        
        Args:
            filters: Dictionary of field:value pairs
            
        Returns:
            Total count
        """
        query = select(func.count()).select_from(self.model)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)
        
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def exists(self, **filters) -> bool:
        """
        Check if record exists with given filters
        
        Args:
            **filters: Field:value pairs
            
        Returns:
            True if exists
        """
        query = select(self.model)
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None
