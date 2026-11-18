"""Strict native XML dates, without locale parsing or invented defaults."""
from datetime import datetime
import re


def xml_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("Tally date must be YYYYMMDD")
    return datetime.strptime(value, "%Y%m%d").date()
