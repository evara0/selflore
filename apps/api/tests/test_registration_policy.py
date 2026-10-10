import pytest
from fastapi import HTTPException

from app.auth import normalize_username, validate_password


@pytest.mark.parametrize("username, expected", [
    ("ABC_123-", "abc_123-"), ("中文用户", "中文用户"), ("123", "123"),
    ("1张三", "1张三"), ("_abc", "_abc"), ("-ab", "-ab"),
    ("a" * 3, "a" * 3), ("a" * 32, "a" * 32),
])
def test_relaxed_usernames(username, expected):
    assert normalize_username(username) == expected


@pytest.mark.parametrize("username", ["", "ab", "a" * 33, "a b", "a.b", "a@b", "用户😀", "éab"])
def test_invalid_usernames(username):
    with pytest.raises(HTTPException) as error:
        normalize_username(username)
    assert error.value.status_code == 422


@pytest.mark.parametrize("length", [0, 7, 8, 12, 128, 129])
def test_relaxed_password_limits(length):
    if 8 <= length <= 128:
        validate_password("a" * length)
    else:
        with pytest.raises(HTTPException) as error:
            validate_password("a" * length)
        assert error.value.status_code == 422
