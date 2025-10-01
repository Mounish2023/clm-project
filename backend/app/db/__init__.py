# backend/db/__init__.py
"""
Database Package

This package contains all database-related modules including models,
configuration, and utilities for the Contract Amendment Orchestrator.
"""

from .databases import (
    engine,
    SessionLocal,
    get_db,
    get_db_context,
    Base,
    create_tables,
    init_database,
    check_database_connection
)

from .models import (
    Contract,
    Amendment,
    ContractVersion,
    WorkflowEvent,
    Party,
    NotificationLog,
)

__all__ = [
    # Database utilities
    'engine',
    'SessionLocal',
    'get_db',
    'get_db_context',
    'Base',
    'create_tables',
    'init_database',
    'check_database_connection',
    
    # Models
    'Contract',
    'Amendment',
    'ContractVersion',
    'WorkflowEvent',
    'Party',
    'NotificationLog',
]