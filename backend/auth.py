# MIGRIGA Authentication & Password Utilities
import hashlib
import secrets

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hashes a password with salt using SHA-256."""
    if not salt:
        salt = secrets.token_hex(16)
    salted = f"{salt}:{password}".encode('utf-8')
    pwd_hash = hashlib.sha256(salted).hexdigest()
    return f"{salt}${pwd_hash}", salt

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a password against the stored salt$hash format."""
    try:
        salt, expected_hash = stored_hash.split('$')
        salted = f"{salt}:{password}".encode('utf-8')
        actual_hash = hashlib.sha256(salted).hexdigest()
        return secrets.compare_digest(actual_hash, expected_hash)
    except Exception:
        return False

def generate_token() -> str:
    """Generates a secure random session token."""
    return secrets.token_urlsafe(32)
