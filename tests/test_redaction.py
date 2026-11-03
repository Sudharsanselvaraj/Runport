"""Tests for extracted PII redaction utilities."""

from runport.datasets.redaction import redact, salted_hash


def test_redaction():
    text = "Please email me at student.test@example.com for assistance."
    clean, counts = redact(text)
    assert "[EMAIL]" in clean
    assert "student.test@example.com" not in clean
    assert counts["[EMAIL]"] == 1

    text2 = "My phone number is +6012-3456789 or 0198765432."
    clean2, counts2 = redact(text2)
    assert "[PHONE]" in clean2
    assert "0198765432" not in clean2

    text3 = "My identity card is 010203-10-1234."
    clean3, counts3 = redact(text3)
    assert "[ID_NUMBER]" in clean3
    assert "010203-10-1234" not in clean3

    text4 = "Hello, my name is John Doe and this is Alice."
    clean4, counts4 = redact(text4)
    assert "[NAME]" in clean4
    assert "John Doe" not in clean4


def test_salted_hash():
    h1 = salted_hash("test-id", "salt-1")
    h2 = salted_hash("test-id", "salt-1")
    h3 = salted_hash("test-id", "salt-2")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16
