# backend/db/database.py
"""
Database Configuration and Connection Management

This module provides database connection, session management, and
initialization utilities for the Contract Amendment Orchestrator.
"""

import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import logging

# Import models to ensure they're registered
from .models import Base, Contract, Amendment, WorkflowEvent, Party, NotificationLog

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://contract_user:contract_pass@localhost:5432/contract_orchestrator"
)

# For testing, allow SQLite
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///./test_contract_orchestrator.db"
)

# Determine if we're in test mode
IS_TESTING = os.getenv("TESTING", "false").lower() == "true"

# Select appropriate database URL
SQLALCHEMY_DATABASE_URL = TEST_DATABASE_URL if IS_TESTING else DATABASE_URL

# Engine configuration
engine_kwargs = {
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",  # Log SQL queries
    "pool_pre_ping": True,  # Verify connections before use
}

# Special configuration for SQLite (testing)
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    })
else:
    # PostgreSQL specific configuration
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),  # 30 minutes
    })

# Create engine
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Set up logging for database events
logging.basicConfig()
db_logger = logging.getLogger("sqlalchemy.engine")


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for testing"""
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session for FastAPI endpoints
    
    Usage in FastAPI:
        @app.get("/endpoint")
        def my_endpoint(db: Session = Depends(get_db)):
            # Use db here
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions
    
    Usage:
        with get_db_context() as db:
            # Use db here
            # Automatic rollback on exception, commit on success
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating database tables: {str(e)}")
        raise


def drop_tables():
    """Drop all database tables (use with caution!)"""
    try:
        Base.metadata.drop_all(bind=engine)
        print("✅ Database tables dropped successfully")
    except Exception as e:
        print(f"❌ Error dropping database tables: {str(e)}")
        raise


def init_database():
    """Initialize database with tables and sample data"""
    print("🔧 Initializing database...")
    
    # Create tables
    create_tables()
    
    # Add sample data in development
    if not IS_TESTING and os.getenv("ENVIRONMENT", "development") == "development":
        create_sample_data()


def create_sample_data():
    """Create sample data for development"""
    print("📝 Creating sample data...")
    
    with get_db_context() as db:
        # Check if sample data already exists
        existing_contract = db.query(Contract).filter(
            Contract.id == "SAMPLE_CONTRACT_001"
        ).first()
        
        if existing_contract:
            print("   Sample data already exists, skipping...")
            return
        
        # Create sample contract
        sample_contract = Contract(
            id="SAMPLE_CONTRACT_001",
            title="Master Service Agreement - Development Services",
            content="""
            MASTER SERVICE AGREEMENT
            
            This Master Service Agreement ("Agreement") is entered into between:
            - TechCorp Inc. (Client)
            - DevStudio LLC (Provider)
            - CloudOps Solutions (Infrastructure Partner)
            
            1. SCOPE OF WORK
            Provider will deliver custom software development services.
            
            2. FINANCIAL TERMS
            Total Project Value: $500,000
            Payment Schedule: Quarterly payments
            Payment Terms: Net 30 days
            
            3. TIMELINE
            Project Start: January 1, 2025
            Estimated Completion: December 31, 2025
            
            4. INTELLECTUAL PROPERTY
            All deliverables will be owned by Client upon payment.
            """,
            contract_type="master_service_agreement",
            parties=[
                {
                    "id": "techcorp_inc",
                    "name": "TechCorp Inc.",
                    "role": "Client",
                    "contact": "legal@techcorp.com"
                },
                {
                    "id": "devstudio_llc", 
                    "name": "DevStudio LLC",
                    "role": "Provider",
                    "contact": "contracts@devstudio.com"
                },
                {
                    "id": "cloudops_solutions",
                    "name": "CloudOps Solutions",
                    "role": "Infrastructure Partner", 
                    "contact": "partnerships@cloudops.com"
                }
            ],
            total_value=500000.00,
            status="active"
        )
        
        db.add(sample_contract)
        
        # Create sample parties
        sample_parties = [
            Party(
                id="techcorp_inc",
                organization_name="TechCorp Inc.",
                organization_type="corporation",
                primary_contact_name="Jane Smith",
                primary_contact_email="legal@techcorp.com",
                policies={
                    "risk_tolerance": "low",
                    "budget_limit": 600000,
                    "approval_threshold": 50000,
                    "required_clauses": ["ip_ownership", "termination_protection"]
                }
            ),
            Party(
                id="devstudio_llc",
                organization_name="DevStudio LLC",
                organization_type="llc",
                primary_contact_name="John Developer",
                primary_contact_email="contracts@devstudio.com",
                policies={
                    "risk_tolerance": "medium",
                    "budget_limit": 750000,
                    "approval_threshold": 75000,
                    "preferred_terms": {"payment_terms": "Net 15 days"}
                }
            ),
            Party(
                id="cloudops_solutions",
                organization_name="CloudOps Solutions",
                organization_type="corporation",
                primary_contact_name="Sarah Cloud",
                primary_contact_email="partnerships@cloudops.com", 
                policies={
                    "risk_tolerance": "high",
                    "budget_limit": 200000,
                    "approval_threshold": 25000
                }
            )
        ]
        
        for party in sample_parties:
            db.add(party)
        
        # Create sample amendment
        sample_amendment = Amendment(
            id="SAMPLE_AMENDMENT_001",
            contract_id="SAMPLE_CONTRACT_001",
            proposed_changes={
                "budget_increase": {
                    "section": "2. FINANCIAL TERMS",
                    "old_value": "$500,000",
                    "new_value": "$650,000",
                    "justification": "Additional security requirements"
                },
                "timeline_extension": {
                    "section": "3. TIMELINE",
                    "old_value": "December 31, 2025",
                    "new_value": "March 31, 2026",
                    "justification": "Extended testing phase"
                }
            },
            parties_involved=["techcorp_inc", "devstudio_llc", "cloudops_solutions"],
            status="completed",
            progress_percentage=100.0
        )
        
        db.add(sample_amendment)
        
        print("   ✅ Sample data created successfully")


def check_database_connection() -> bool:
    """Check if database connection is working"""
    try:
        with get_db_context() as db:
            # Simple query to test connection
            db.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False


def get_database_info() -> dict:
    """Get database connection information"""
    return {
        "url": SQLALCHEMY_DATABASE_URL.split("@")[-1] if "@" in SQLALCHEMY_DATABASE_URL else SQLALCHEMY_DATABASE_URL,
        "is_testing": IS_TESTING,
        "pool_size": engine.pool.size() if hasattr(engine.pool, 'size') else "N/A",
        "checked_out": engine.pool.checkedout() if hasattr(engine.pool, 'checkedout') else "N/A",
        "overflow": engine.pool.overflow() if hasattr(engine.pool, 'overflow') else "N/A",
    }


class DatabaseManager:
    """Database management utility class"""
    
    @staticmethod
    def health_check() -> dict:
        """Perform database health check"""
        try:
            with get_db_context() as db:
                # Test basic connectivity
                db.execute("SELECT 1")
                
                # Get table counts
                contract_count = db.query(Contract).count()
                amendment_count = db.query(Amendment).count()
                event_count = db.query(WorkflowEvent).count()
                
                return {
                    "status": "healthy",
                    "connection": "ok",
                    "tables": {
                        "contracts": contract_count,
                        "amendments": amendment_count,
                        "events": event_count
                    },
                    "info": get_database_info()
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connection": "failed",
                "error": str(e),
                "info": get_database_info()
            }
    
    @staticmethod
    def cleanup_old_data(days_old: int = 90):
        """Clean up old data (use with caution)"""
        print(f"🧹 Cleaning up data older than {days_old} days...")
        
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        with get_db_context() as db:
            # Clean up old workflow events
            old_events = db.query(WorkflowEvent).filter(
                WorkflowEvent.timestamp < cutoff_date
            ).count()
            
            if old_events > 0:
                db.query(WorkflowEvent).filter(
                    WorkflowEvent.timestamp < cutoff_date
                ).delete()
                print(f"   Deleted {old_events} old workflow events")
            
            # Clean up old notifications
            old_notifications = db.query(NotificationLog).filter(
                NotificationLog.created_at < cutoff_date
            ).count()
            
            if old_notifications > 0:
                db.query(NotificationLog).filter(
                    NotificationLog.created_at < cutoff_date
                ).delete()
                print(f"   Deleted {old_notifications} old notifications")
            
            print("   ✅ Cleanup completed")


# Initialize database on import if not testing
if not IS_TESTING and os.getenv("AUTO_INIT_DB", "true").lower() == "true":
    try:
        if check_database_connection():
            init_database()
    except Exception as e:
        print(f"⚠️  Database auto-initialization failed: {str(e)}")
        print("   Database will need to be initialized manually")


# Export commonly used items
__all__ = [
    'engine',
    'SessionLocal', 
    'get_db',
    'get_db_context',
    'Base',
    'create_tables',
    'init_database',
    'DatabaseManager',
    'check_database_connection'
]