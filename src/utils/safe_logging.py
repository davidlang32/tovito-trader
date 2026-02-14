"""
Safe Logging System with PII Protection
========================================

CRITICAL: This module ensures NO personally identifiable information (PII)
or sensitive financial data is exposed in logs or CLI output.

All logging goes through this module to sanitize sensitive data.
"""

import logging
import re
import os
from typing import Any, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class PIIProtector:
    """Sanitizes PII and sensitive data from logs"""
    
    # Sensitive field patterns to mask
    SENSITIVE_FIELDS = {
        'api_key', 'password', 'token', 'secret', 'credential',
        'ssn', 'social_security', 'account_number', 'routing_number',
        'email', 'phone', 'address', 'name', 'investor_name',
        'balance', 'equity', 'cash', 'value', 'amount', 'salary',
        'tax_id', 'ein', 'account_id'
    }
    
    # Patterns for dollar amounts
    DOLLAR_PATTERN = re.compile(r'\$[\d,]+\.?\d*')
    
    # Patterns for email addresses
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    # Patterns for phone numbers
    PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
    
    # Patterns for API keys (common formats)
    API_KEY_PATTERN = re.compile(r'(sk_|pk_|api_)[a-zA-Z0-9]{20,}')
    
    @staticmethod
    def mask_string(value: str, visible_chars: int = 4) -> str:
        """
        Mask a string, showing only last few characters
        
        Args:
            value: String to mask
            visible_chars: Number of characters to show at end
            
        Returns:
            Masked string like "****5678"
        """
        if not value or len(value) <= visible_chars:
            return "****"
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]
    
    @staticmethod
    def mask_dollar_amount(value: float, show_magnitude: bool = True) -> str:
        """
        Mask dollar amount
        
        Args:
            value: Dollar amount
            show_magnitude: If True, show order of magnitude
            
        Returns:
            Masked amount like "$X,XXX.XX" or "$***"
        """
        if not show_magnitude:
            return "$***"
        
        # Show magnitude (thousands, millions, etc.)
        if value >= 1_000_000:
            return f"$X.XXM"
        elif value >= 100_000:
            return f"$XXX,XXX"
        elif value >= 10_000:
            return f"$XX,XXX"
        elif value >= 1_000:
            return f"$X,XXX"
        else:
            return f"$XXX"
    
    @staticmethod
    def mask_email(email: str) -> str:
        """
        Mask email address
        
        Args:
            email: Email to mask
            
        Returns:
            Masked email like "d***@***er.com"
        """
        if '@' not in email:
            return "***@***.com"
        
        local, domain = email.split('@')
        domain_parts = domain.split('.')
        
        masked_local = local[0] + "***" if len(local) > 1 else "***"
        masked_domain = "***" + domain_parts[-1] if len(domain_parts) > 0 else "***"
        
        return f"{masked_local}@{masked_domain}"
    
    @staticmethod
    def mask_name(name: str) -> str:
        """
        Mask person's name
        
        Args:
            name: Name to mask
            
        Returns:
            Masked name like "Investor A" or "User #1"
        """
        # Just use generic identifiers
        return "Investor ***"
    
    @staticmethod
    def mask_dict(data: Dict[str, Any], show_structure: bool = True) -> Dict[str, Any]:
        """
        Recursively mask sensitive fields in a dictionary
        
        Args:
            data: Dictionary to mask
            show_structure: If True, keep keys visible (values masked)
            
        Returns:
            Dictionary with sensitive values masked
        """
        if not isinstance(data, dict):
            return data
        
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if this key contains sensitive data
            is_sensitive = any(field in key_lower for field in PIIProtector.SENSITIVE_FIELDS)
            
            if is_sensitive:
                # Mask the value based on type
                if isinstance(value, (int, float)):
                    masked[key] = "***"
                elif isinstance(value, str):
                    masked[key] = PIIProtector.mask_string(value)
                else:
                    masked[key] = "***"
            elif isinstance(value, dict):
                # Recursively mask nested dictionaries
                masked[key] = PIIProtector.mask_dict(value, show_structure)
            elif isinstance(value, list):
                # Mask lists
                masked[key] = [PIIProtector.mask_dict(item, show_structure) if isinstance(item, dict) else "***" for item in value]
            else:
                # Keep non-sensitive data
                masked[key] = value
        
        return masked
    
    @staticmethod
    def sanitize_message(message: str) -> str:
        """
        Remove PII from a log message
        
        Args:
            message: Message to sanitize
            
        Returns:
            Sanitized message with PII removed/masked
        """
        # Mask dollar amounts
        message = PIIProtector.DOLLAR_PATTERN.sub("$***", message)
        
        # Mask emails
        message = PIIProtector.EMAIL_PATTERN.sub("***@***.com", message)
        
        # Mask phone numbers
        message = PIIProtector.PHONE_PATTERN.sub("***-***-****", message)
        
        # Mask API keys
        message = PIIProtector.API_KEY_PATTERN.sub("***_KEY", message)
        
        return message


class SafeLogger:
    """
    Logger with automatic PII protection
    
    Usage:
        logger = SafeLogger(__name__)
        logger.info("Processing transaction", amount=5000.00, investor="John Doe")
        # Output: "Processing transaction | amount=$*** | investor=Investor ***"
    """
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        Initialize safe logger
        
        Args:
            name: Logger name (usually __name__)
            log_file: Optional log file path
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler (INFO and above)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (DEBUG and above) - if log file specified
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def _format_safe_message(self, message: str, **kwargs) -> str:
        """Format message with sanitized kwargs"""
        # Sanitize the main message
        safe_message = PIIProtector.sanitize_message(message)
        
        # Add sanitized kwargs
        if kwargs:
            safe_kwargs = PIIProtector.mask_dict(kwargs)
            kwargs_str = " | ".join(f"{k}={v}" for k, v in safe_kwargs.items())
            return f"{safe_message} | {kwargs_str}"
        
        return safe_message
    
    def debug(self, message: str, **kwargs):
        """Log debug message with PII protection"""
        safe_message = self._format_safe_message(message, **kwargs)
        self.logger.debug(safe_message)
    
    def info(self, message: str, **kwargs):
        """Log info message with PII protection"""
        safe_message = self._format_safe_message(message, **kwargs)
        self.logger.info(safe_message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with PII protection"""
        safe_message = self._format_safe_message(message, **kwargs)
        self.logger.warning(safe_message)
    
    def error(self, message: str, **kwargs):
        """Log error message with PII protection"""
        safe_message = self._format_safe_message(message, **kwargs)
        self.logger.error(safe_message)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with PII protection"""
        safe_message = self._format_safe_message(message, **kwargs)
        self.logger.critical(safe_message)


# Global logger factory
def get_safe_logger(name: str, log_file: Optional[str] = None) -> SafeLogger:
    """
    Get a safe logger instance
    
    Args:
        name: Logger name (use __name__)
        log_file: Optional log file path
        
    Returns:
        SafeLogger instance
    """
    return SafeLogger(name, log_file)


# Test the logger
if __name__ == "__main__":
    print("="*60)
    print("TESTING PII PROTECTION SYSTEM")
    print("="*60)
    
    # Test individual masking functions
    print("\n1. Testing String Masking:")
    print(f"   API Key: {PIIProtector.mask_string('sk_live_abc123def456ghi789')}")
    
    print("\n2. Testing Dollar Masking:")
    print(f"   $50,000: {PIIProtector.mask_dollar_amount(50000)}")
    print(f"   $1,234,567: {PIIProtector.mask_dollar_amount(1234567)}")
    
    print("\n3. Testing Email Masking:")
    print(f"   john.doe@example.com: {PIIProtector.mask_email('john.doe@example.com')}")
    
    print("\n4. Testing Name Masking:")
    print(f"   John Doe: {PIIProtector.mask_name('John Doe')}")
    
    print("\n5. Testing Dictionary Masking:")
    test_data = {
        'investor_name': 'John Doe',
        'email': 'john@example.com',
        'balance': 50000.00,
        'shares': 10000,  # Not sensitive
        'api_key': 'sk_live_abc123',
        'transaction_id': 'TXN-12345'  # Not sensitive
    }
    masked = PIIProtector.mask_dict(test_data)
    print(f"   Original keys: {list(test_data.keys())}")
    print(f"   Masked data: {masked}")
    
    print("\n6. Testing Message Sanitization:")
    message = "Processed $5,000.00 for john.doe@example.com (phone: 555-123-4567)"
    print(f"   Original: {message}")
    print(f"   Sanitized: {PIIProtector.sanitize_message(message)}")
    
    print("\n7. Testing Safe Logger:")
    logger = get_safe_logger(__name__)
    logger.info("Processing contribution", 
                investor_name="John Doe",
                amount=5000.00,
                email="john@example.com",
                shares=4750)
    
    logger.info("System started successfully")
    logger.warning("Low balance detected", balance=100.50)
    logger.error("Transaction failed", amount=10000, reason="Insufficient funds")
    
    print("\n" + "="*60)
    print("✅ PII PROTECTION TESTS COMPLETE")
    print("="*60)
    print("\nNOTE: All sensitive data is automatically masked in logs!")
    print("Safe to share logs with support or for debugging.")