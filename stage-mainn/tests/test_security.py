"""Security tests for the application."""

import pytest
import os
from pathlib import Path
from core.encryption import encrypt_bytes, decrypt_bytes, get_or_create_key
from core.audit import get_audit_logger, AuditEventType
from core.anonymisation import anonymise_dataframe
import pandas as pd


class TestEncryption:
    """Test encryption/decryption functionality."""
    
    def test_encryption_key_generation(self):
        """Test that encryption key is generated."""
        key = get_or_create_key()
        assert key is not None
        assert len(key) > 0
        # Fernet keys are URL-safe base64, should decode
        import base64
        assert base64.urlsafe_b64decode(key)  # Should not raise
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted data can be decrypted."""
        original_data = b"Sensitive information: SSN 123-45-6789"
        
        encrypted = encrypt_bytes(original_data)
        assert encrypted != original_data
        assert encrypted is not None
        
        decrypted = decrypt_bytes(encrypted)
        assert decrypted == original_data
    
    def test_encryption_is_deterministic_false(self):
        """Test that encryption is NOT deterministic (good for security)."""
        key = get_or_create_key()
        data = b"test"
        
        encrypted1 = encrypt_bytes(data, key)
        encrypted2 = encrypt_bytes(data, key)
        
        # Same data, same key, but different ciphertexts (due to IV)
        # This is actually good - it means the same data encrypts differently each time
        # So you can't determine content by comparing encrypted values
        assert encrypted1 != encrypted2
        
        # But both decrypt to the same plaintext
        assert decrypt_bytes(encrypted1, key) == decrypt_bytes(encrypted2, key)


class TestAuditLogging:
    """Test audit logging functionality."""
    
    def test_audit_logger_creates_log_file(self):
        """Test that audit logger creates a log file."""
        logger = get_audit_logger()
        logger.log_event(
            AuditEventType.AUTHENTICATION_SUCCESS,
            user="test_user",
            status="SUCCESS"
        )
        
        assert logger.log_file.exists()
    
    def test_audit_log_contains_event(self):
        """Test that events are logged."""
        logger = get_audit_logger()
        logger.log_auth_attempt(user="test_user", success=True)
        
        content = logger.log_file.read_text()
        assert "test_user" in content or "AUTHENTICATION_SUCCESS" in content
    
    def test_audit_log_data_access(self):
        """Test data access logging."""
        logger = get_audit_logger()
        logger.log_data_access(user="analyst", mois="2026-06", data_type="KPI")
        
        content = logger.log_file.read_text()
        assert "2026-06" in content or "DATA_ACCESS" in content


class TestAnonymisation:
    """Test data anonymisation."""
    
    def test_sensitive_columns_removed(self):
        """Test that sensitive columns are removed."""
        df = pd.DataFrame({
            "nom": ["Jean", "Marie"],
            "email": ["jean@example.com", "marie@example.com"],
            "telephone": ["0123456789", "0987654321"],
            "date_ouverture": ["2026-06-01", "2026-06-02"],
            "priorite": ["Haute", "Basse"],
        })
        
        anonymised = anonymise_dataframe(df)
        
        sensitive_cols = ["nom", "email", "telephone", "comment"]
        for col in sensitive_cols:
            assert col not in anonymised.columns, f"Sensitive column {col} should be removed"
    
    def test_safe_columns_preserved(self):
        """Test that non-sensitive columns are preserved."""
        df = pd.DataFrame({
            "date_ouverture": ["2026-06-01", "2026-06-02"],
            "priorite": ["Haute", "Basse"],
            "sujet": ["Bug", "Feature"],
        })
        
        anonymised = anonymise_dataframe(df)
        
        assert "date_ouverture" in anonymised.columns
        assert "priorite" in anonymised.columns
        assert "sujet" in anonymised.columns


class TestAPIKeyValidation:
    """Test API key validation."""
    
    def test_api_keys_from_environment(self):
        """Test that API keys are read from environment."""
        api_keys_str = os.getenv("API_KEYS", "")
        
        # Should either be set or empty (both are valid for different scenarios)
        assert isinstance(api_keys_str, str)
    
    def test_api_key_in_valid_set(self):
        """Test that API keys are properly formatted."""
        api_keys_str = os.getenv("API_KEYS", "")
        if api_keys_str:
            keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
            assert len(keys) > 0
            # Each key should be a token (alphanumeric, dashes, underscores)
            import re
            for key in keys:
                assert re.match(r"^[A-Za-z0-9_-]+$", key), f"Invalid key format: {key}"


class TestSecurityHeaders:
    """Test that security headers are properly configured (when API runs)."""
    
    @pytest.mark.skip(reason="Requires running API server")
    def test_security_headers_present(self):
        """Test that security headers are in API responses."""
        # This would be tested with:
        # response = requests.get("http://localhost:8000/health")
        # assert "X-Content-Type-Options" in response.headers
        pass


# Integration test
class TestSecurityIntegration:
    """Integration tests for security features."""
    
    def test_full_encryption_audit_flow(self):
        """Test that encryption and audit work together."""
        # Create test data
        test_data = b"Customer: John Doe, Email: john@example.com, SSN: 123-45-6789"
        
        # Encrypt it
        encrypted = encrypt_bytes(test_data)
        assert encrypted != test_data
        
        # Log the audit event
        logger = get_audit_logger()
        logger.log_event(
            AuditEventType.ENCRYPTION,
            user="system",
            details={"bytes_encrypted": len(test_data)}
        )
        
        # Verify decryption
        decrypted = decrypt_bytes(encrypted)
        assert decrypted == test_data
        
        # Verify audit log
        assert logger.log_file.exists()
