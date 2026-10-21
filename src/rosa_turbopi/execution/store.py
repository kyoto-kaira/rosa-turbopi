"""Process-local execution history."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class Run:
    query: str
    id: str = field(default_factory=lambda: uuid4().hex)
    state: str = "running"
    reply: str = ""
    calls: list = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
