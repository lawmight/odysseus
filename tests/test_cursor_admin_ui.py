from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent


def test_cursor_provider_option_and_workspace_input_exist():
    soup = BeautifulSoup((ROOT / "static/index.html").read_text(encoding="utf-8"), "html.parser")

    provider = soup.select_one("#adm-epProvider option[value='cursor://local']")
    workspace = soup.select_one("#adm-epCursorCwd")
    row = soup.select_one("#adm-epCursorRow")

    assert provider is not None
    assert provider.text.strip() == "Cursor (local)"
    assert workspace is not None
    assert "Workspace directory for Cursor bridge" in workspace.get("placeholder", "")
    assert row is not None
    assert "hidden" in row.get("class", [])


def test_admin_js_toggles_cursor_workspace_row():
    js = (ROOT / "static/js/admin.js").read_text(encoding="utf-8")

    assert "provider.value === 'cursor://local'" in js
    assert "cursorRow.classList.toggle('hidden', !isCursor)" in js
    assert "provider.value && !isCursor && !apiKey" in js
    assert "Cursor API key is required" in js
    assert "fd.append('provider', 'cursor')" in js
    assert "fd.append('cursor_cwd', cursorCwd.value.trim())" in js
