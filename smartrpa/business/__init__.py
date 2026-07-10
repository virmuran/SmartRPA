"""SmartRPA business logic layer.

Provides task management, history storage, and other
business-level abstractions above the core engine.
"""
from smartrpa.business.task_manager import TaskManager
from smartrpa.business.history import HistoryStore

__all__ = ["TaskManager", "HistoryStore"]
