from llm_obs.pii.redact import redact


def test_redacts_email():
    text = "Contact me at alice@example.com please"
    redacted, detections = redact(text)
    assert "alice@example.com" not in redacted
    assert any(d["type"] == "email" for d in detections)
