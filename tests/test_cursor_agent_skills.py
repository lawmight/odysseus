"""Plan B backlog B2b: Cursor agent sessions omit the manage_skills index."""

from types import SimpleNamespace

from src.chat_processor import ChatProcessor


class _Memory:
    def load(self, owner=None):
        return []


class _Skills:
    def index_for(self, owner=None):
        return [{"name": "demo", "category": "general", "description": "a demo skill"}]


def _processor():
    return ChatProcessor(
        memory_manager=_Memory(),
        personal_docs_manager=SimpleNamespace(rag_manager=None),
        skills_manager=_Skills(),
    )


def _preface_text(session):
    proc = _processor()
    preface, _rag, _web = proc.build_context_preface(
        message="hello",
        session=session,
        use_web=False,
        use_memory=False,
        agent_mode=True,
        incognito=False,
        use_skills=True,
    )
    return "\n".join(m.get("content", "") for m in preface)


def test_skills_index_omitted_for_cursor_agent():
    session = SimpleNamespace(endpoint_url="cursor://local")
    assert "Available skills" not in _preface_text(session)
    assert "manage_skills" not in _preface_text(session)


def test_skills_index_present_for_native_agent():
    session = SimpleNamespace(endpoint_url="https://api.openai.com/v1")
    assert "Available skills" in _preface_text(session)
