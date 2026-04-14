from weekchef.observability.redact import intake_text_hash


def test_intake_text_hash_stable():
    t = "hello world"
    assert intake_text_hash(t) == intake_text_hash(t)
    assert len(intake_text_hash(t)) == 16
