"""
Tovito Trader Test Suite

Comprehensive regression testing for the Tovito Trader system.

Test Categories:
- NAV Calculations: Core mathematical calculations
- Contributions: Share purchase and allocation
- Withdrawals: Tax calculations and share reduction
- Database: CRUD operations and integrity
- Validation: Data consistency checks

Run all tests:
    python run.py test

Run specific test file:
    pytest tests/test_nav_calculations.py

Run with markers:
    pytest -m critical
    pytest -m "unit and calculations"
"""

__version__ = "1.0.0"
