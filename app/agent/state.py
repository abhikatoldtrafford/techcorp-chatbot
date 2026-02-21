from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class ConversationState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[dict] = field(default_factory=list)
    is_authenticated: bool = False
    customer_id: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    turn_count: int = 0

    def reset(self):
        """Reset to unauthenticated state and clear history."""
        self.messages.clear()
        self.is_authenticated = False
        self.customer_id = None
        self.customer_name = None
        self.customer_email = None
        self.turn_count = 0
