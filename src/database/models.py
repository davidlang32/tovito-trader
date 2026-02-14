"""
Database Models
Defines the structure of all database tables
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class Investor(Base):
    """Investor account information"""
    __tablename__ = 'investors'
    
    investor_id = Column(String(20), primary_key=True)  # '20260101-01A'
    name = Column(String(100), nullable=False)
    initial_capital = Column(Float, nullable=False)
    join_date = Column(Date, nullable=False)
    status = Column(String(20), default='Active')  # Active, Inactive, Pending
    current_shares = Column(Float, default=0.0)
    net_investment = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    transactions = relationship('Transaction', back_populates='investor')
    tax_events = relationship('TaxEvent', back_populates='investor')
    
    def __repr__(self):
        return f"<Investor(id={self.investor_id}, name={self.name}, status={self.status})>"


class DailyNAV(Base):
    """Daily Net Asset Value tracking"""
    __tablename__ = 'daily_nav'
    
    date = Column(Date, primary_key=True)
    nav_per_share = Column(Float, nullable=False)
    total_portfolio_value = Column(Float, nullable=False)
    total_shares = Column(Float, nullable=False)
    daily_change_dollars = Column(Float, default=0.0)
    daily_change_percent = Column(Float, default=0.0)
    source = Column(String(20), default='Manual')  # Manual, API, Imported
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<DailyNAV(date={self.date}, nav={self.nav_per_share:.4f}, value={self.total_portfolio_value:.2f})>"


class Transaction(Base):
    """All investor transactions"""
    __tablename__ = 'transactions'
    
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    investor_id = Column(String(20), ForeignKey('investors.investor_id'), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # Initial, Contribution, Withdrawal
    amount = Column(Float, nullable=False)
    share_price = Column(Float, nullable=False)
    shares_transacted = Column(Float, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    investor = relationship('Investor', back_populates='transactions')
    
    def __repr__(self):
        return f"<Transaction(id={self.transaction_id}, investor={self.investor_id}, type={self.transaction_type}, amount={self.amount:.2f})>"


class TaxEvent(Base):
    """Tax events from withdrawals with gains"""
    __tablename__ = 'tax_events'
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    investor_id = Column(String(20), ForeignKey('investors.investor_id'), nullable=False)
    withdrawal_amount = Column(Float, nullable=False)
    realized_gain = Column(Float, nullable=False)
    tax_due = Column(Float, nullable=False)
    net_proceeds = Column(Float, nullable=False)
    tax_rate = Column(Float, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    investor = relationship('Investor', back_populates='tax_events')
    
    def __repr__(self):
        return f"<TaxEvent(id={self.event_id}, investor={self.investor_id}, gain={self.realized_gain:.2f}, tax={self.tax_due:.2f})>"


class SystemLog(Base):
    """System logs and automation history"""
    __tablename__ = 'system_logs'
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    log_type = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, SUCCESS
    category = Column(String(50), nullable=False)  # DailyUpdate, Transaction, Report, Email
    message = Column(Text, nullable=False)
    details = Column(Text)
    
    def __repr__(self):
        return f"<SystemLog(timestamp={self.timestamp}, type={self.log_type}, category={self.category})>"


class EmailLog(Base):
    """Email delivery tracking"""
    __tablename__ = 'email_logs'
    
    email_id = Column(Integer, primary_key=True, autoincrement=True)
    sent_at = Column(DateTime, default=datetime.now, nullable=False)
    recipient = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    email_type = Column(String(50), nullable=False)  # MonthlyReport, Newsletter, Alert
    status = Column(String(20), default='Sent')  # Sent, Failed, Pending
    error_message = Column(Text)
    
    def __repr__(self):
        return f"<EmailLog(recipient={self.recipient}, type={self.email_type}, status={self.status})>"


# Database initialization and helper functions
class Database:
    """Database management and operations"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', 'data/tovito.db')
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.Session = sessionmaker(bind=self.engine)
    
    def create_all_tables(self):
        """Create all tables in the database"""
        Base.metadata.create_all(self.engine)
        print("✅ All database tables created successfully")
    
    def get_session(self):
        """Get a new database session"""
        return self.Session()
    
    def drop_all_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(self.engine)
        print("⚠️  All tables dropped")


# Test and initialization
if __name__ == "__main__":
    """Initialize database with tables"""
    
    print("Initializing Tovito Trader Database...")
    
    db = Database()
    db.create_all_tables()
    
    # Test creating a session
    session = db.get_session()
    
    # Check if tables exist
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print(f"\n✅ Database initialized with {len(tables)} tables:")
    for table in tables:
        print(f"   - {table}")
    
    session.close()
    print("\n🎉 Database setup complete!")
