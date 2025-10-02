# backend/db/database.py
"""
Database Configuration and Connection Management

This module provides database connection, session management, and
initialization utilities for the Contract Amendment Orchestrator.
"""

import os
from typing import Generator
from rich import text
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import logging

# Import models to ensure they're registered
from .models import Base, Contract, Amendment, Party, ContractVersion
from datetime import datetime

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
        # Check if sample data already exists (check for first party)
# Define sample IDs for deletion
        party_ids = [
            "techcorp_inc",
            "devstudio_llc",
            "cloudops_solutions",
            "fintech_innovations_ltd",
            "healthcare_systems_corp",
            "ecogreen_energy_llc",
            "autodrive_technologies_inc",
            "foodchain_distributors",
            "mediastream_entertainment",
            "securenet_cybersecurity_llc"
        ]
         
# Check if sample data already exists (check for first party)
        existing_party = db.query(Party).filter(
            Party.id == "techcorp_inc"
        ).first()
        
        if existing_party:
            print("   Clearing existing sample data...")
            
            # Delete all versions (no filter, deletes everything in the table)
            db.query(ContractVersion).delete(synchronize_session=False)
            
            # Delete all amendments
            db.query(Amendment).delete(synchronize_session=False)
            
            # Delete all contracts
            db.query(Contract).delete(synchronize_session=False)
            
            # Delete all parties
            db.query(Party).delete(synchronize_session=False)
            
            db.commit()
            print("   Existing data cleared.")
        
        # Create 10 sample parties with realistic data
        sample_parties = [
            Party(
                id="techcorp_inc",
                organization_name="TechCorp Inc.",
                organization_type="corporation",
                primary_contact_name="Jane Smith",
                primary_contact_email="legal@techcorp.com",
                primary_contact_phone="+1-555-123-4567",
                policies={
                    "risk_tolerance": "low",
                    "budget_limit": 600000,
                    "approval_threshold": 50000,
                    "required_clauses": ["ip_ownership", "termination_protection"]
                },
                preferences={
                    "notification_method": "email",
                    "frequency": "weekly"
                },
                status="active",
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="devstudio_llc",
                organization_name="DevStudio LLC",
                organization_type="llc",
                primary_contact_name="John Developer",
                primary_contact_email="contracts@devstudio.com",
                primary_contact_phone="+1-555-234-5678",
                policies={
                    "risk_tolerance": "medium",
                    "budget_limit": 750000,
                    "approval_threshold": 75000,
                    "preferred_terms": {"payment_terms": "Net 15 days"}
                },
                preferences={
                    "notification_method": "slack",
                    "frequency": "daily"
                },
                status="active",
                created_at=datetime(2024, 2, 15),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="cloudops_solutions",
                organization_name="CloudOps Solutions",
                organization_type="corporation",
                primary_contact_name="Sarah Cloud",
                primary_contact_email="partnerships@cloudops.com",
                primary_contact_phone="+1-555-345-6789",
                policies={
                    "risk_tolerance": "high",
                    "budget_limit": 200000,
                    "approval_threshold": 25000
                },
                preferences={
                    "notification_method": "email",
                    "frequency": "monthly"
                },
                status="active",
                created_at=datetime(2024, 3, 10),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="fintech_innovations_ltd",
                organization_name="FinTech Innovations Ltd.",
                organization_type="llc",
                primary_contact_name="Mike Finance",
                primary_contact_email="mike@fintechinn.com",
                primary_contact_phone="+1-555-456-7890",
                policies={
                    "risk_tolerance": "medium",
                    "budget_limit": 1000000,
                    "approval_threshold": 100000,
                    "required_clauses": ["data_privacy", "compliance"]
                },
                preferences={
                    "notification_method": "email",
                    "frequency": "weekly"
                },
                status="active",
                created_at=datetime(2024, 4, 5),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="healthcare_systems_corp",
                organization_name="HealthCare Systems Corp.",
                organization_type="corporation",
                primary_contact_name="Dr. Emily Health",
                primary_contact_email="emily@healthcaresys.com",
                primary_contact_phone="+1-555-567-8901",
                policies={
                    "risk_tolerance": "low",
                    "budget_limit": 500000,
                    "approval_threshold": 40000,
                    "required_clauses": ["hipaa_compliance", "liability"]
                },
                preferences={
                    "notification_method": "phone",
                    "frequency": "as_needed"
                },
                status="active",
                created_at=datetime(2024, 5, 20),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="ecogreen_energy_llc",
                organization_name="EcoGreen Energy LLC",
                organization_type="llc",
                primary_contact_name="Tom Green",
                primary_contact_email="tom@ecogreen.com",
                primary_contact_phone="+1-555-678-9012",
                policies={
                    "risk_tolerance": "high",
                    "budget_limit": 300000,
                    "approval_threshold": 30000
                },
                preferences={
                    "notification_method": "email",
                    "frequency": "biweekly"
                },
                status="active",
                created_at=datetime(2024, 6, 15),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="autodrive_technologies_inc",
                organization_name="AutoDrive Technologies Inc.",
                organization_type="corporation",
                primary_contact_name="Lisa Drive",
                primary_contact_email="lisa@autodrive.com",
                primary_contact_phone="+1-555-789-0123",
                policies={
                    "risk_tolerance": "medium",
                    "budget_limit": 800000,
                    "approval_threshold": 60000,
                    "preferred_terms": {"warranty": "2 years"}
                },
                preferences={
                    "notification_method": "slack",
                    "frequency": "daily"
                },
                status="active",
                created_at=datetime(2024, 7, 10),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="foodchain_distributors",
                organization_name="FoodChain Distributors",
                organization_type="partnership",
                primary_contact_name="Bob Food",
                primary_contact_email="bob@foodchain.com",
                primary_contact_phone="+1-555-890-1234",
                policies={
                    "risk_tolerance": "low",
                    "budget_limit": 400000,
                    "approval_threshold": 35000
                },
                preferences={
                    "notification_method": "email",
                    "frequency": "weekly"
                },
                status="active",
                created_at=datetime(2024, 8, 5),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="mediastream_entertainment",
                organization_name="MediaStream Entertainment",
                organization_type="corporation",
                primary_contact_name="Alice Media",
                primary_contact_email="alice@mediastream.com",
                primary_contact_phone="+1-555-901-2345",
                policies={
                    "risk_tolerance": "high",
                    "budget_limit": 900000,
                    "approval_threshold": 70000,
                    "required_clauses": ["content_ownership"]
                },
                preferences={
                    "notification_method": "phone",
                    "frequency": "monthly"
                },
                status="active",
                created_at=datetime(2024, 9, 20),
                updated_at=datetime(2025, 10, 1)
            ),
            Party(
                id="securenet_cybersecurity_llc",
                organization_name="SecureNet Cybersecurity LLC",
                organization_type="llc",
                primary_contact_name="David Secure",
                primary_contact_email="david@securenet.com",
                primary_contact_phone="+1-555-012-3456",
                policies={
                    "risk_tolerance": "medium",
                    "budget_limit": 550000,
                    "approval_threshold": 45000
                },
                preferences={
                    "notification_method": "email",
                    "frequency": "daily"
                },
                status="active",
                created_at=datetime(2024, 10, 15),
                updated_at=datetime(2025, 10, 1)
            )
        ]
        
        for party in sample_parties:
            db.add(party)
        
        # Define party IDs for reuse
        party_ids = [p.id for p in sample_parties]
        
        # Create 10 sample contracts, each with 2-3 parties
        sample_contracts = []
        for i in range(10):
            # Cycle through parties
            p1 = party_ids[i % 10]
            p2 = party_ids[(i + 1) % 10]
            p3 = party_ids[(i + 2) % 10] if i % 2 == 0 else None  # Some with 3 parties
            parties_list = [
                {
                    "id": p1,
                    "name": sample_parties[i % 10].organization_name,
                    "role": "Client",
                    "contact": sample_parties[i % 10].primary_contact_email
                },
                {
                    "id": p2,
                    "name": sample_parties[(i + 1) % 10].organization_name,
                    "role": "Provider",
                    "contact": sample_parties[(i + 1) % 10].primary_contact_email
                }
            ]
            if p3:
                parties_list.append({
                    "id": p3,
                    "name": sample_parties[(i + 2) % 10].organization_name,
                    "role": "Partner",
                    "contact": sample_parties[(i + 2) % 10].primary_contact_email
                })
            
            contract = Contract(
                id=f"SAMPLE_CONTRACT_{i+1:03d}",
                title=f"Agreement {i+1}: {sample_parties[i % 10].organization_name} Services",
                content=f"""
                MASTER SERVICE AGREEMENT {i+1}
                
                This Agreement is entered into between:
                - {parties_list[0]['name']} ({parties_list[0]['role']})
                - {parties_list[1]['name']} ({parties_list[1]['role']})
                {f"- {parties_list[2]['name']} ({parties_list[2]['role']})" if p3 else ""}
                
                1. SCOPE OF WORK
                Provider will deliver services as specified.
                
                2. FINANCIAL TERMS
                Total Value: ${50000 * (i+1)}
                Payment Schedule: Monthly
                
                3. TIMELINE
                Start: {datetime(2025, 1, 1 + i).strftime('%B %d, %Y')}
                End: {datetime(2025, 12, 31 - i).strftime('%B %d, %Y')}
                
                4. INTELLECTUAL PROPERTY
                Ownership terms apply.
                """,
                content_hash=f"hash_contract_{i+1:03d}",
                contract_type="service_agreement" if i % 2 == 0 else "supply_agreement",
                parties=parties_list,
                primary_contact=parties_list[0]['contact'],
                status="active" if i % 3 == 0 else "draft" if i % 3 == 1 else "terminated",
                version=1,
                total_value=50000 * (i + 1),
                currency="USD",
                effective_date=datetime(2025, 1, 1 + i),
                expiration_date=datetime(2025, 12, 31 - i),
                created_at=datetime(2025, 1, 1 + i),
                updated_at=datetime(2025, 10, 1)
            )
            db.add(contract)
            sample_contracts.append(contract)
        
        # Create 10 sample amendments, one per contract
        sample_amendments = []
        for i in range(10):
            contract_id = sample_contracts[i].id
            p1 = party_ids[i % 10]
            p2 = party_ids[(i + 1) % 10]
            p3 = party_ids[(i + 2) % 10] if i % 2 == 0 else None
            involved = [p1, p2]
            if p3:
                involved.append(p3)
            
            amendment = Amendment(
                id=f"SAMPLE_AMENDMENT_{i+1:03d}",
                contract_id=contract_id,
                proposed_changes={
                    f"change_{i+1}_1": {
                        "section": "2. FINANCIAL TERMS",
                        "old_value": f"${50000 * (i+1)}",
                        "new_value": f"${50000 * (i+1) + 10000}",
                        "justification": "Increased scope"
                    },
                    f"change_{i+1}_2": {
                        "section": "3. TIMELINE",
                        "old_value": datetime(2025, 12, 31 - i).strftime('%B %d, %Y'),
                        "new_value": datetime(2026, 3, 31 - i).strftime('%B %d, %Y'),
                        "justification": "Additional requirements"
                    }
                },
                parties_involved=involved,
                status="completed" if i % 3 == 0 else "initiated" if i % 3 == 1 else "rejected",
                approvals={p1: {"approved": True, "date": "2025-09-01"}, p2: {"approved": i % 2 == 0, "date": "2025-09-02"}},
                conflicts=[{"issue": f"Disagreement on change {i+1}", "resolution": "pending" if i % 2 == 0 else "resolved"}],
                legal_review_status="completed" if i % 2 == 0 else "pending",
                compliance_checks={"gdpr": "passed", "sox": "passed" if i % 2 == 0 else "failed"},
                risk_assessment={"level": "medium", "score": 5.0 + i * 0.5},
                final_document=f"Amended content for contract {contract_id}.",
                final_document_hash=f"hash_amend_{i+1:03d}",
                error_log=[{"error": "Validation warning", "timestamp": "2025-08-01"}] if i % 3 == 0 else None,
                retry_count=i % 4,
                workflow_config={"steps": ["initiate", "review", "approve"]},
                created_at=datetime(2025, 6, 1 + i),
                updated_at=datetime(2025, 10, 1),
                completed_at=datetime(2025, 9, 1 + i) if i % 3 == 0 else None
            )
            db.add(amendment)
            sample_amendments.append(amendment)
        
        # Create 10 sample contract versions, one per contract
        for i in range(10):
            contract_id = sample_contracts[i].id
            amendment_id = sample_amendments[i].id if i % 2 == 0 else None
            version = ContractVersion(
                id=f"SAMPLE_VERSION_{i+1:03d}",
                contract_id=contract_id,
                amendment_id=amendment_id,
                version_number=2 if amendment_id else 1,
                content=f"Version content for contract {contract_id}, version {2 if amendment_id else 1}. Updated terms.",
                content_hash=f"hash_version_{i+1:03d}",
                changes_summary=f"Summary of changes for version {i+1}.",
                diff_from_previous={"added": ["new section"], "removed": [], "modified": ["financial terms"]},
                author="System Admin" if i % 2 == 0 else "Legal Team",
                author_type="system" if i % 2 == 0 else "user",
                tags=["approved"] if i % 3 == 0 else ["draft"],
                contract_metadata={"notes": f"Metadata for version {i+1}"},
                created_at=datetime(2025, 2, 1 + i) if not amendment_id else datetime(2025, 7, 1 + i)
            )
            db.add(version)
        
        db.commit()
        print("   ✅ Sample data created successfully")

def check_database_connection() -> bool:
    """Check if database connection is working"""
    try:
        with get_db_context() as db:
            # Simple query to test connection
            db.execute(text("SELECT 1"))
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


# class DatabaseManager:
#     """Database management utility class"""
    
#     @staticmethod
#     def health_check() -> dict:
#         """Perform database health check"""
#         try:
#             with get_db_context() as db:
#                 # Test basic connectivity
#                 db.execute("SELECT 1")
                
#                 # Get table counts
#                 contract_count = db.query(Contract).count()
#                 amendment_count = db.query(Amendment).count()
#                 event_count = db.query(WorkflowEvent).count()
                
#                 return {
#                     "status": "healthy",
#                     "connection": "ok",
#                     "tables": {
#                         "contracts": contract_count,
#                         "amendments": amendment_count,
#                         "events": event_count
#                     },
#                     "info": get_database_info()
#                 }
#         except Exception as e:
#             return {
#                 "status": "unhealthy",
#                 "connection": "failed",
#                 "error": str(e),
#                 "info": get_database_info()
#             }
    
#     @staticmethod
#     def cleanup_old_data(days_old: int = 90):
#         """Clean up old data (use with caution)"""
#         print(f"🧹 Cleaning up data older than {days_old} days...")
        
#         from datetime import timedelta
#         cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
#         with get_db_context() as db:
#             # Clean up old workflow events
#             old_events = db.query(WorkflowEvent).filter(
#                 WorkflowEvent.timestamp < cutoff_date
#             ).count()
            
#             if old_events > 0:
#                 db.query(WorkflowEvent).filter(
#                     WorkflowEvent.timestamp < cutoff_date
#                 ).delete()
#                 print(f"   Deleted {old_events} old workflow events")
            
#             # Clean up old notifications
#             old_notifications = db.query(NotificationLog).filter(
#                 NotificationLog.created_at < cutoff_date
#             ).count()
            
#             if old_notifications > 0:
#                 db.query(NotificationLog).filter(
#                     NotificationLog.created_at < cutoff_date
#                 ).delete()
#                 print(f"   Deleted {old_notifications} old notifications")
            
#             print("   ✅ Cleanup completed")


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
    'check_database_connection'
]