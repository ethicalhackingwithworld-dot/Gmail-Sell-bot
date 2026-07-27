"""Handlers package"""
from app.handlers.start_handler import router as start_router
from app.handlers.task_handler import router as task_router

__all__ = ["start_router", "task_router"]
