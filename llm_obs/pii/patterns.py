import re
from dataclasses import dataclass


@dataclass
class PIIPattern:
    name: str
    pattern: re.Pattern[str]
    placeholder: str
    validate: "callable | None" = None


def _compile(p: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(p, flags)


PATTERNS: list[PIIPattern] = [
    PIIPattern(
        name="email",
        pattern=_compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b"),
        placeholder="[REDACTED_EMAIL]",
    ),
    PIIPattern(
        name="phone",
        pattern=_compile(r"(\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"),
        placeholder="[REDACTED_PHONE]",
    ),
    PIIPattern(
        name="ssn",
        pattern=_compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"),
        placeholder="[REDACTED_SSN]",
    ),
    PIIPattern(
        name="credit_card",
        pattern=_compile(r"\b(?:\d[ \-]?){13,19}\b"),
        placeholder="[REDACTED_CARD]",
    ),
    PIIPattern(
        name="ipv4",
        pattern=_compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
        placeholder="[REDACTED_IP]",
    ),
    PIIPattern(
        name="api_key",
        pattern=_compile(r"\b(sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9\-_]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_\-]{35})\b"),
        placeholder="[REDACTED_API_KEY]",
    ),
    PIIPattern(
        name="url_secret",
        # Capture the key name in group 1, redact only the value
        pattern=_compile(r"((?:token|api_?key|password|secret|key)=)[^\s&\"']+"),
        placeholder=r"\1[REDACTED]",
    ),
]
