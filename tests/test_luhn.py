from llm_obs.pii.luhn import luhn_valid


def test_luhn_valid_visa_test_number():
    assert luhn_valid("4111111111111111")


def test_luhn_rejects_invalid():
    assert not luhn_valid("4111111111111112")


def test_luhn_requires_minimum_length():
    assert not luhn_valid("123")
