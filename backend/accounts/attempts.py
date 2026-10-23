import hashlib

from django.core.cache import cache

FAILURE_LIMIT = 5
LOCK_SECONDS = 120


class SignInAttempts:
    def __init__(self, request, email):
        address = request.META.get("REMOTE_ADDR", "") if request else ""
        # Memcached and Redis reject long keys or keys with spaces, so the email is hashed.
        fingerprint = hashlib.sha256(f"{address}|{email.strip().lower()}".encode()).hexdigest()
        self.cache_key = f"sign-in-failures:{fingerprint}"

    @property
    def is_locked(self):
        return cache.get(self.cache_key, 0) >= FAILURE_LIMIT

    def record_failure(self):
        cache.set(self.cache_key, cache.get(self.cache_key, 0) + 1, LOCK_SECONDS)

    def clear(self):
        cache.delete(self.cache_key)
