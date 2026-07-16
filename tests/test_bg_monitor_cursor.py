"""bg_monitor must not run the native agent loop on Cursor sessions."""

import asyncio
from types import SimpleNamespace

import pytest

from src import bg_monitor


class _FakeSessionManager:
    def __init__(self, session):
        self._session = session

    def get_session(self, sid):
        return self._session


def _run(coro):
    return asyncio.run(coro)


def test_followup_skips_cursor_session(monkeypatch):
    """A Cursor-backed session is marked handled without invoking the native loop."""
    session = SimpleNamespace(id="s1", endpoint_url="cursor://local", model="composer-2.5")

    # A sibling test may replace src.ai_interaction in sys.modules with a bare
    # stub, so set the attribute with raising=False to work either way.
    import src.ai_interaction as ai_interaction
    monkeypatch.setattr(
        ai_interaction, "get_session_manager",
        lambda: _FakeSessionManager(session), raising=False,
    )

    drained = {"called": False}

    async def _fake_drain(sess, messages):
        drained["called"] = True
        return "", []

    monkeypatch.setattr(bg_monitor, "_drain_agent", _fake_drain)

    rec = {"id": "job1", "session_id": "s1"}
    handled = _run(bg_monitor._run_followup(rec))

    assert handled is True
    assert drained["called"] is False


def test_followup_runs_native_for_non_cursor_session(monkeypatch):
    """A normal HTTP session still drives the native agent loop."""
    session = SimpleNamespace(
        id="s2",
        endpoint_url="https://api.openai.com/v1",
        model="gpt-4o",
        owner=None,
    )
    session.get_context_messages = lambda: []

    saved = {"messages": []}

    class _SM(_FakeSessionManager):
        def add_message(self, sid, msg):
            saved["messages"].append(msg)

        def save_sessions(self):
            pass

    import src.ai_interaction as ai_interaction
    from src import bg_jobs
    monkeypatch.setattr(
        ai_interaction, "get_session_manager", lambda: _SM(session), raising=False,
    )
    monkeypatch.setattr(bg_jobs, "result_text", lambda rec: "job output", raising=False)

    drained = {"called": False}

    async def _fake_drain(sess, messages):
        drained["called"] = True
        return "continued", []

    monkeypatch.setattr(bg_monitor, "_drain_agent", _fake_drain)

    rec = {"id": "job2", "session_id": "s2"}
    handled = _run(bg_monitor._run_followup(rec))

    assert handled is True
    assert drained["called"] is True
    assert saved["messages"]
