# context.py
from contextvars import ContextVar
from typing import Optional, Dict

_user_ctx_var: ContextVar[Optional[Dict]] = ContextVar("user", default=None)


def set_current_user(user: Dict):
    _user_ctx_var.set(user)


def get_current_user() -> Optional[Dict]:
    return _user_ctx_var.get()
