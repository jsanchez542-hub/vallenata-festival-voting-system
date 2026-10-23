import hashlib
from contextlib import suppress

from django.contrib.auth import get_user_model
from django.core.cache import cache

ACCOUNT_FAILURE_LIMIT = 5
ADDRESS_FAILURE_LIMIT = 20
WINDOW_SECONDS = 120


def cache_key(*parts):
    # Memcached and Redis reject long keys or keys with spaces, so the parts are hashed.
    return "sign-in:" + hashlib.sha256("|".join(parts).encode()).hexdigest()


def increment(key):
    cache.add(key, 0, WINDOW_SECONDS)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, WINDOW_SECONDS)
        return 1


class SignInAttempts:
    def __init__(self, request, email):
        address = request.META.get("REMOTE_ADDR", "") if request else ""
        email = email.strip()
        # Resolve the account with the same lookup as sign-in, so variants of an email that
        # the database collation treats as equal (case, accents) share one counter.
        account = (
            get_user_model()
            .objects.filter(email__iexact=email)
            .values_list("pk", flat=True)
            .first()
        )
        target = f"account:{account}" if account else f"email:{email.lower()}"
        self.account_key = cache_key(address, target)
        self.address_key = cache_key(address)

    def start(self):
        within_account = increment(self.account_key) <= ACCOUNT_FAILURE_LIMIT
        within_address = increment(self.address_key) <= ADDRESS_FAILURE_LIMIT
        return within_account and within_address

    def succeeded(self):
        cache.delete(self.account_key)
        with suppress(ValueError):
            cache.decr(self.address_key)
