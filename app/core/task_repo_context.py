"""
Request-scoped :class:`TaskRepository` binding for graph nodes.

The compiled LangGraph is shared application-wide; checkpoint persistence uses
the repository from the current async request via a context variable.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from app.repositories.task_repo import TaskRepository

_task_repo_ctx: ContextVar[TaskRepository | None] = ContextVar("task_repo", default=None)


def set_current_task_repo(repo: TaskRepository) -> Token[TaskRepository | None]:
    """Bind ``repo`` for the current task; returns a token for :func:`reset_current_task_repo`."""
    return _task_repo_ctx.set(repo)


def reset_current_task_repo(token: Token[TaskRepository | None]) -> None:
    """Restore the previous repository binding."""
    _task_repo_ctx.reset(token)


def get_current_task_repo() -> TaskRepository:
    """Return the bound task repository or raise if none is set."""
    repo = _task_repo_ctx.get()
    if repo is None:
        msg = "Task repository is not bound in context"
        raise RuntimeError(msg)
    return repo
