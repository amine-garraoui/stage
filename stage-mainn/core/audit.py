"""Audit logging for sensitive operations."""

import logging
import json
from datetime import datetime
from pathlib import Path
from enum import Enum


class AuditEventType(Enum):
    """Types of events to audit."""
    DATA_ACCESS = "DATA_ACCESS"  # Someone read KPI data
    DATA_EXPORT = "DATA_EXPORT"  # PDF/Excel generated
    AUTHENTICATION_SUCCESS = "AUTH_SUCCESS"
    AUTHENTICATION_FAILURE = "AUTH_FAILURE"
    ENCRYPTION = "ENCRYPTION"
    DECRYPTION = "DECRYPTION"


class AuditLogger:
    """Centralized audit log for compliance and security."""
    
    def __init__(self, log_file: Path = Path("data/audit.log")):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create separate audit logger
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event_type: AuditEventType, user: str = "system", 
                  details: dict = None, status: str = "SUCCESS"):
        """Log an audit event."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "user": user,
            "status": status,
            "details": details or {}
        }
        
        self.logger.info(json.dumps(log_entry))
    
    def log_data_access(self, user: str, mois: str, data_type: str = "KPI"):
        """Log when someone accesses sensitive data."""
        self.log_event(
            AuditEventType.DATA_ACCESS,
            user=user,
            details={
                "data_type": data_type,
                "month": mois
            }
        )
    
    def log_export(self, user: str, mois: str, format: str = "PDF"):
        """Log when someone exports data."""
        self.log_event(
            AuditEventType.DATA_EXPORT,
            user=user,
            details={
                "format": format,
                "month": mois
            }
        )
    
    def log_auth_attempt(self, user: str, success: bool):
        """Log authentication attempts."""
        event_type = (AuditEventType.AUTHENTICATION_SUCCESS 
                     if success 
                     else AuditEventType.AUTHENTICATION_FAILURE)
        self.log_event(
            event_type,
            user=user,
            status="SUCCESS" if success else "FAILURE"
        )


# Global audit logger instance
_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    return _audit_logger
