"""
Plan Classification Module
============================

Categorizes portfolio positions into investment plans:
- Plan CASH: Treasury/money market (SGOV, cash, short-duration)
- Plan ETF: Index ETF strategy (SPY, QQQ, SPXL, TQQQ)
- Plan A: Leveraged options strategy (all other positions)
"""

from .classification import classify_position, get_plan_metadata, PLAN_IDS
