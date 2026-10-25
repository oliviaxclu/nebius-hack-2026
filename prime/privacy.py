"""Redaction applied to EVERYTHING before it leaves the device.

Direct identifiers (name, DOB, MRN, phone, email, SSN) are replaced with placeholders.
Clinical dates and values are deliberately kept: the model needs them to reason about trends.
That trade-off is shown to the user via the audit log (`vitae audit`).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")


def _dob_variants(iso: str) -> list[str]:
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
    except ValueError:
        return [iso]
    return list({iso, d.strftime("%m/%d/%Y"), d.strftime("%-m/%-d/%Y"), d.strftime("%B %-d, %Y"), d.strftime("%b %-d, %Y")})


class Redactor:
    def __init__(self, identity: dict[str, list[str]] | None = None):
        identity = identity or {}
        self._rules: list[tuple[re.Pattern, str]] = []

        # 1) structured identifiers first, so e.g. an email containing the patient's name is
        #    replaced whole instead of being partially mangled by the name rules.
        for em in identity.get("email", []):
            self._rules.append((re.compile(re.escape(em), re.I), "[EMAIL]"))
        for ph in identity.get("phone", []):
            self._rules.append((re.compile(re.escape(ph)), "[PHONE]"))
        for mrn in identity.get("mrn", []):
            self._rules.append((re.compile(re.escape(mrn), re.I), "[MRN]"))
        for dob in identity.get("dob", []):
            for v in _dob_variants(dob):
                self._rules.append((re.compile(re.escape(v), re.I), "[DOB]"))
        self._rules += [(SSN, "[SSN]"), (EMAIL, "[EMAIL]"), (PHONE, "[PHONE]")]

        # 2) then names (longest first)
        names = set()
        for n in identity.get("name", []):
            names.add(n)
            names.update(t for t in re.split(r"\s+", n) if len(t) >= 3)
        for n in sorted(names, key=len, reverse=True):
            self._rules.append((re.compile(rf"\b{re.escape(n)}\b", re.I), "[PATIENT]"))

    def redact(self, text: str) -> str:
        for pat, repl in self._rules:
            text = pat.sub(repl, text)
        return text

    def redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, list):
            return [self.redact_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        return obj
