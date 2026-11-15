import hashlib

from app.services.store import hash_phone


def test_phone_hash_is_stable_and_ignores_formatting():
    assert hash_phone("+1 (214) 555-0100") == hash_phone("12145550100")


def test_phone_hash_is_keyed_not_plain_sha256():
    plain = hashlib.sha256(b"12145550100").hexdigest()
    assert hash_phone("+1 214 555 0100") != plain


def test_phone_hash_none_for_missing_phone():
    assert hash_phone(None) is None
    assert hash_phone("") is None
