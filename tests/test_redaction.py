"""Behavioral equivalence test for extracted PII redaction."""

from runport.classification.dataprep import redact as legacy_redact
from runport.datasets.redaction import redact as new_redact


def test_redaction_equivalence():
    samples = [
        "Please email me at student.test@university.edu.my for assistance.",
        "My phone number is +6012-3456789 or 0198765432.",
        "My identity card is 010203-10-1234.",
        "Hello, my name is John Doe and this is Alice.",
        "No personal information here.",
        "Contact my father's name is Robert Smith at 012-9988776",
    ]
    for sample in samples:
        leg_text, leg_counts = legacy_redact(sample)
        new_text, new_counts = new_redact(sample)
        assert leg_text == new_text
        assert dict(leg_counts) == dict(new_counts)
