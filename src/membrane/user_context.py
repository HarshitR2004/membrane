"""User context injected into scoped managers."""

from __future__ import annotations

from typing import Any

from membrane.users import User


class UserContext:
    """Request-scoped context containing the current user."""

    def __init__(
        self,
        user_id: str,
        username: str,
        wallet: str | None,
        namespace: str,
    ) -> None:
        self.user_id = user_id
        self.username = username
        self.wallet = wallet
        self.namespace = namespace

    @property
    def owner(self) -> str:
        """The owner string to use for records (wallet or username)."""
        return self.wallet if self.wallet else self.username


def build_user_context(user: User) -> UserContext:
    """Build a UserContext from a User model."""
    return UserContext(
        user_id=user.id,
        username=user.username,
        wallet=user.wallet_address,
        namespace=user.namespace,
    )
