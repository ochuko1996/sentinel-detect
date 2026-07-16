from sentinel_detect.security.passwords import hash_password, verify_password


def test_hash_password_is_not_the_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_the_correct_password() -> None:
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    hashed = hash_password("s3cret!")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_a_malformed_hash_instead_of_raising() -> None:
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_hashing_the_same_password_twice_produces_different_hashes() -> None:
    # bcrypt salts each hash independently.
    assert hash_password("same-password") != hash_password("same-password")
