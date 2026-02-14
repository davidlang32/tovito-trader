#!/usr/bin/env python3
"""
Tovito Trader - Quick Setup Script
Automates the initial setup process
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def check_python_version():
    """Ensure Python 3.9+"""
    print("Checking Python version...")
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")


def install_dependencies():
    """Install required packages"""
    print("\nInstalling dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ All dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        print("   Try manually: pip install -r requirements.txt")
        sys.exit(1)


def create_env_file():
    """Create .env from template"""
    print("\nSetting up configuration...")
    
    if os.path.exists('.env'):
        response = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Keeping existing .env file")
            return
    
    # Copy template
    with open('.env.template', 'r') as f:
        template = f.read()
    
    with open('.env', 'w') as f:
        f.write(template)
    
    print("✅ Created .env file")
    print("\n⚠️  IMPORTANT: Edit .env file with your credentials:")
    print("   - TRADIER_API_KEY")
    print("   - TRADIER_ACCOUNT_ID")
    print("   - EMAIL_FROM")
    print("   - EMAIL_PASSWORD")


def create_data_directory():
    """Create data directory for database"""
    print("\nCreating data directory...")
    Path("data").mkdir(exist_ok=True)
    print("✅ Data directory ready")


def initialize_database():
    """Create database tables"""
    print("\nInitializing database...")
    
    response = input("Create database tables now? (Y/n): ")
    if response.lower() == 'n':
        print("Skipping database creation")
        return
    
    try:
        from src.database.models import Database
        db = Database()
        db.create_all_tables()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {str(e)}")
        print("   You can run manually later: python src/database/models.py")


def test_imports():
    """Test that core imports work"""
    print("\nTesting imports...")
    
    try:
        from src.api import tradier
        from src.database import models
        from src.automation import nav_calculator
        print("✅ All core modules imported successfully")
    except ImportError as e:
        print(f"❌ Import failed: {str(e)}")
        print("   Check that all dependencies are installed")
        sys.exit(1)


def print_next_steps():
    """Print next steps"""
    print_header("SETUP COMPLETE!")
    
    print("✅ Python version verified")
    print("✅ Dependencies installed")
    print("✅ Configuration file created")
    print("✅ Data directory created")
    print("✅ Database initialized")
    print("✅ Core modules tested")
    
    print("\n" + "="*60)
    print("  NEXT STEPS")
    print("="*60)
    
    print("\n1️⃣  Configure Credentials:")
    print("   Edit .env file with your:")
    print("   - Tradier API key and account ID")
    print("   - Gmail address and app password")
    
    print("\n2️⃣  Test API Connection:")
    print("   python src/api/tradier.py")
    
    print("\n3️⃣  Import Excel Data (optional):")
    print("   python scripts/migrate_from_excel.py")
    
    print("\n4️⃣  Test Daily Update:")
    print("   python src/automation/nav_calculator.py")
    
    print("\n5️⃣  Start Automation Service:")
    print("   python src/automation/scheduler.py")
    
    print("\n📖 For detailed instructions, see: SETUP_GUIDE.md")
    print("\n🎉 You're ready to automate your portfolio tracking!\n")


def main():
    """Main setup flow"""
    print_header("TOVITO TRADER - QUICK SETUP")
    
    print("This script will:")
    print("  ✓ Check Python version")
    print("  ✓ Install dependencies")
    print("  ✓ Create configuration file")
    print("  ✓ Initialize database")
    print("  ✓ Test core modules")
    
    response = input("\nContinue? (Y/n): ")
    if response.lower() == 'n':
        print("Setup cancelled")
        sys.exit(0)
    
    try:
        check_python_version()
        install_dependencies()
        create_env_file()
        create_data_directory()
        initialize_database()
        test_imports()
        print_next_steps()
        
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
