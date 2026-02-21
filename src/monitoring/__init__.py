"""
Monitoring Module
=================
Reusable health-check data layer for operations monitoring.

The HealthCheckService class provides system health queries as plain
Python dicts/lists so any UI (Streamlit, CustomTkinter, API) can consume
them without coupling to a presentation framework.
"""

from src.monitoring.health_checks import HealthCheckService, get_remediation

__all__ = ['HealthCheckService', 'get_remediation']
