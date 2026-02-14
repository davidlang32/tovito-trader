"""
Safe Formatter - Context-Aware PII Display
===========================================

Formats sensitive data differently based on context:
- INTERACTIVE mode: Shows real values (when you're running commands)
- LOGGED mode: Masks values (for logs and automation)

This allows you to see real data in UI while keeping logs safe to share.

Usage:
    from src.utils.safe_formatter import SafeFormatter
    
    # In interactive scripts
    formatter = SafeFormatter(mode="INTERACTIVE")
    print(f"Amount: {formatter.currency(5000)}")  # Shows: $5,000.00
    
    # In automated scripts/logs
    formatter = SafeFormatter(mode="LOGGED")
    print(f"Amount: {formatter.currency(5000)}")  # Shows: $***
"""

import os
from typing import Any, Optional


class SafeFormatter:
    """Context-aware formatter for PII protection"""
    
    # Display modes
    INTERACTIVE = "INTERACTIVE"  # Show real values (UI)
    LOGGED = "LOGGED"           # Mask values (logs, automation)
    
    def __init__(self, mode: str = LOGGED):
        """
        Initialize formatter
        
        Args:
            mode: Display mode (INTERACTIVE or LOGGED)
        """
        self.mode = mode
    
    def currency(self, amount: Optional[float], decimals: int = 2) -> str:
        """
        Format currency with masking
        
        Args:
            amount: Dollar amount
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        if amount is None:
            return "$0.00" if self.mode == self.INTERACTIVE else "$***"
        
        if self.mode == self.INTERACTIVE:
            return f"${amount:,.{decimals}f}"
        else:
            return "$***"
    
    def shares(self, shares: Optional[float], decimals: int = 4) -> str:
        """
        Format share count with masking
        
        Args:
            shares: Number of shares
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        if shares is None:
            return "0.0000" if self.mode == self.INTERACTIVE else "***"
        
        if self.mode == self.INTERACTIVE:
            return f"{shares:,.{decimals}f}"
        else:
            return "***"
    
    def percentage(self, pct: Optional[float], decimals: int = 2) -> str:
        """
        Format percentage with masking
        
        Args:
            pct: Percentage value
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        if pct is None:
            return "0.00%" if self.mode == self.INTERACTIVE else "***%"
        
        if self.mode == self.INTERACTIVE:
            return f"{pct:,.{decimals}f}%"
        else:
            return "***%"
    
    def name(self, name: Optional[str]) -> str:
        """
        Format investor name with masking
        
        Args:
            name: Investor name
        
        Returns:
            Formatted string
        """
        if not name:
            return "Unknown" if self.mode == self.INTERACTIVE else "Investor ***"
        
        if self.mode == self.INTERACTIVE:
            return name
        else:
            return "Investor ***"
    
    def investor_id(self, investor_id: str) -> str:
        """
        Format investor ID (always shown for identification)
        
        Args:
            investor_id: Investor ID
        
        Returns:
            Formatted string (never masked)
        """
        return investor_id
    
    def number(self, num: Optional[float], decimals: int = 2) -> str:
        """
        Format generic number with masking
        
        Args:
            num: Number value
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        if num is None:
            return "0.00" if self.mode == self.INTERACTIVE else "***"
        
        if self.mode == self.INTERACTIVE:
            return f"{num:,.{decimals}f}"
        else:
            return "***"
    
    def is_interactive(self) -> bool:
        """Check if in interactive mode"""
        return self.mode == self.INTERACTIVE
    
    def is_logged(self) -> bool:
        """Check if in logged mode"""
        return self.mode == self.LOGGED


def get_display_mode() -> str:
    """
    Determine display mode based on environment
    
    Returns:
        INTERACTIVE or LOGGED
    """
    # Check if running interactively
    # If stdin is a terminal, we're interactive
    # If not, we're probably in automation/logging
    import sys
    
    if sys.stdin.isatty():
        return SafeFormatter.INTERACTIVE
    else:
        return SafeFormatter.LOGGED


def get_formatter(mode: Optional[str] = None) -> SafeFormatter:
    """
    Get formatter with auto-detected mode
    
    Args:
        mode: Override mode (optional)
    
    Returns:
        SafeFormatter instance
    """
    if mode is None:
        mode = get_display_mode()
    
    return SafeFormatter(mode=mode)


# Convenience functions for quick formatting
def format_currency(amount: float, mode: Optional[str] = None) -> str:
    """Quick currency format"""
    formatter = get_formatter(mode)
    return formatter.currency(amount)


def format_shares(shares: float, mode: Optional[str] = None) -> str:
    """Quick shares format"""
    formatter = get_formatter(mode)
    return formatter.shares(shares)


def format_percentage(pct: float, mode: Optional[str] = None) -> str:
    """Quick percentage format"""
    formatter = get_formatter(mode)
    return formatter.percentage(pct)


def format_name(name: str, mode: Optional[str] = None) -> str:
    """Quick name format"""
    formatter = get_formatter(mode)
    return formatter.name(name)


# Example usage
if __name__ == "__main__":
    print("SafeFormatter - Context-Aware PII Display")
    print("=" * 50)
    print()
    
    # Test in both modes
    for mode in [SafeFormatter.INTERACTIVE, SafeFormatter.LOGGED]:
        formatter = SafeFormatter(mode=mode)
        print(f"Mode: {mode}")
        print("-" * 50)
        print(f"Currency:   {formatter.currency(12345.67)}")
        print(f"Shares:     {formatter.shares(10000.5678)}")
        print(f"Percentage: {formatter.percentage(15.234)}")
        print(f"Name:       {formatter.name('John Smith')}")
        print(f"ID:         {formatter.investor_id('20260101-01A')}")
        print()
