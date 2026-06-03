# Cursor SDK × Odysseus capability matrix

**Last updated:** 2026-06-02  
**Odysseus branch:** `main` @ `edb2495`  
**Purpose:** Inventory every major Cursor Python SDK capability and map it to what Odysseus implements today. Use this to scope Plan C+, Plan B, and avoid surprise gaps.

**Nia sources used:**

| ID | Resource |
|----|----------|
| `71741e4c-d188-415c-b114-0c6a5b656526` | [Cursor Python SDK](https://cursor.com/docs/sdk/python) |
| `abe7140b-c0c5-4e3b-899c-04826a0d02a5` | [Cloud Agents REST API](https://cursor.com/docs/cloud-agent/api/endpoints) |
| `5c39f490-db62-4a02-a6df-8db343f8b597` | `lawmight/odysseus` @ `main` (Nia repo index) |

**Related plans:** [README](./README.md) · [Plan C+](./cursor-useful-tools-plan.md) · [Plan B](./cursor-agent-tab-integration-plan.md) · [Verification sheet](./CURSOR_INTEGRATION_VERIFICATION.md)

---

## Legend

| Odysseus status | Meaning |
|-----------------|---------|
| **shipped** | Implemented and covered by tests or clear production path |
| **partial** | Wired but incomplete (missing events, UI, or edge cases) |
| **gap** | Not implemented; user-visible hole |
| **blocked** | Intentionally rejected for product reasons |
| **n/a** | Out of Odysseus v1 scope |

| Target plan | Meaning |
|-------------|---------|
| **A/C** | Shipped with Plan A/C Chat BYOK |
| **C+** | [cursor-useful-tools-plan.md](./cursor-useful-tools-plan.md) |
| **B** | [cursor-agent-tab-integration-plan.md](./cursor-agent-tab-integration-plan.md) |
| **Phase 2** | Plan C polish (ACK, README, rate-limit copy) |
| **Phase 3** | REST fallback, cloud runtime, advanced recovery |
| **wont-fix** | Explicitly out of scope for this fork v1 |

---

## Summary

| Status | Count |
|--------|------:|
| shipped | 28 |
| partial | 6 |
| gap | 22 |
| blocked | 4 |
| n/a | 20 |
| **Total rows** | **80** |

### Top gaps by user impact (fix or plan next)

1. **`tool_call` / `generateImage` → Chat UI** — SDK runs tools; Odysseus drops events (**C+**)
2. **`SendOptions.mode` (plan/agent)** — Agent tab Cursor engine (**B**)
3. **Full tool mapping → `tool_start` / `tool_output`** — Agent tab (**B**)
4. **`SendOptions.mcp_servers`** — Cursor MCP vs Odysseus MCP admin (**B** / Phase 3)
5. **`ModelSelection.params`** — thinking effort / model variants in admin (**Phase 2**)
6. **`local.force`** — recover stuck local runs (**Phase 2**)
7. **410 `stream_expired` recovery** — poll run after SSE dies (**Phase 3**)
8. **Cloud agents / repos / PRs** — separate product surface (**wont-fix** v1)

### Plan C+ checklist (filter `Target plan = C+`)

| Row ID | Must become |
|--------|-------------|
| `stream.tool_call` | Map `SDKToolUseMessage` in Chat (allowlist) |
| `tool.generateImage` | Emit `image_url` SSE + serve asset from uploads/gallery |
| `stream.status` | Optional: status line or ignore (document choice) |

---

## 1. Runtime and authentication

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `runtime.local` | Local runtime (`LocalAgentOptions`, `launch_bridge`) | Async, local | shipped | `cursor_adapter._get_bridge_client`, `stream_cursor_chat` | Chat uses local bridge against `provider_config.cwd` | A/C | Requires bridge on Odysseus host |
| `runtime.cloud_hosted` | Cloud Cursor-hosted VMs (`CloudAgentOptions`) | Cloud | n/a | — | Not used | wont-fix | Plan docs defer cloud |
| `runtime.cloud_self_hosted` | Self-hosted pool (`CloudEnvironment`) | Cloud | n/a | — | Not used | wont-fix | Enterprise pool |
| `auth.user_key` | User API key (`CURSOR_API_KEY` / endpoint row) | Both | shipped | `model_routes`, `extract_cursor_api_key` | Encrypted on `ModelEndpoint`; Bearer/Basic on models API | A/C | BYOK via admin |
| `auth.service_account` | Service account keys | Both | partial | Same as user key | Same code path; no distinct UI copy | Phase 2 | SDK supports; Odysseus treats as generic key |
| `auth.admin_key` | Team Admin API keys | Both | gap | — | No pre-flight rejection message | Phase 2 | SDK docs: not supported |
| `billing.sdk_tag` | Usage under SDK tag in dashboard | Both | n/a | — | Documented in admin only | Phase 2 | No runtime check |

---

## 2. Client lifecycle

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `client.async_launch_bridge` | `AsyncClient.launch_bridge(workspace)` | Async | shipped | `cursor_adapter._get_bridge_client` | Cached per cwd (`CURSOR_BRIDGE_CACHE_MAX`) | A/C | |
| `client.connect` | `AsyncClient.connect(base_url, auth_token)` | Async | gap | — | Always spawns bridge | Phase 3 | Sidecar / Docker pattern in Plan C doc |
| `client.bridge_cache` | Reuse bridge clients per workspace | Async | shipped | `_bridge_clients` OrderedDict | LRU eviction + shutdown close | A/C | `close_cursor_bridges()` on app shutdown |
| `client.with_options` | `client.with_options(timeout, max_retries)` | Async | gap | — | Default SDK timeouts only | Phase 3 | |
| `client.custom_httpx` | Custom httpx client / proxy | Async | gap | — | Not exposed | wont-fix | |
| `client.sync_default` | Sync `close_default_client()` | Sync | n/a | — | Odysseus uses async path only | n/a | |
| `client.resource_agents` | `client.agents.create/resume/list/get` | Async | partial | `create`, `resume` only | No list/get/archive from Odysseus UI | B / Phase 3 | |

---

## 3. Agent lifecycle

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `agent.create` | `client.agents.create(model, api_key, local=…)` | Async | shipped | `stream_cursor_chat` | First Chat turn when no `cursor_agent_id` | A/C | |
| `agent.resume` | `client.agents.resume(agent_id, opts)` | Async | shipped | `stream_cursor_chat`, `session_manager` | Follow-up turns; ID in `sessions.cursor_agent_id` | A/C | Pass `model` on send |
| `agent.agent_id` | Persist `agent_id` (`agent-*` local, `bc-*` cloud) | Async | shipped | `core/database.py`, `llm_core.py` | Saved on first create via SSE + session manager | A/C | |
| `agent.close` | Context manager / `agent.close()` | Async | shipped | `async with agent` in `stream_cursor_chat` | Released after each send | A/C | |
| `agent.reload` | Re-read `.cursor` hooks/MCP/subagents | Async | gap | — | Not called | B | Useful after MCP file edits |
| `agent.list_messages` | `agent.list_messages()` | Async | gap | — | History via SDK agent, not exposed in UI | Phase 3 | |
| `agent.prompt_oneshot` | `Agent.prompt()` / `AsyncAgent.prompt()` | Async | n/a | — | Not used | n/a | Odysseus uses durable agent |
| `agent.archive` | Cloud archive | Cloud | n/a | — | — | wont-fix | |
| `agent.unarchive` | Cloud unarchive | Cloud | n/a | — | — | wont-fix | |
| `agent.delete` | Cloud delete | Cloud | n/a | — | — | wont-fix | |
| `agent.subagents` | `AgentOptions.agents` subagent defs | Both | gap | — | — | B / Phase 3 | |

---

## 4. Run and streaming

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `run.send` | `agent.send(message, options)` | Async | shipped | `stream_cursor_chat` | Passes `{"model": model}` on send | A/C | |
| `run.messages` | `async for event in run.messages()` | Async | partial | `stream_cursor_chat` | Handles `assistant`, `thinking`, `tool_call` (allowlist), `error` | B | Chat maps `generateImage` only |
| `run.events` | `run.events()` / `RunStreamEvent` | Async | gap | — | Not used | Phase 3 | Lower-level than messages |
| `run.iter_text` | `run.iter_text()` | Async | gap | — | Manual delta mapping instead | n/a | Equivalent via assistant blocks |
| `run.text` | `await run.text()` | Async | gap | — | Streaming only in Chat | n/a | |
| `run.wait` | `await run.wait()` → `RunResult` | Async | gap | — | Stream-to-completion inline | Phase 3 | Needed for 410 recovery |
| `run.cancel` | `await run.cancel()` | Async | shipped | `cancel_cursor_run`, `chat_routes` stop | Wired to chat stop endpoint | A/C | |
| `run.conversation` | `run.conversation()` / JSON | Async | gap | — | Not persisted from SDK turns | Phase 3 | |
| `run.observe` | `run.observe(after_offset=…)` | Async | gap | — | — | Phase 3 | REST stream resume |
| `run.status_fields` | `run.status`, `duration_ms`, `result` | Async | partial | `stream_cursor_chat` | Emits `usage.total_time` only; no tokens | Phase 2 | SDK may omit token counts |
| `run.git` | `run.git` / `RunGitInfo` (cloud) | Cloud | n/a | — | — | wont-fix | |
| `run.on_step` | `SendOptions.on_step` | Async | gap | — | — | B | Maps to `agent_step` |
| `run.on_delta` | `SendOptions.on_delta` | Async | gap | — | — | Phase 3 | Raw `InteractionUpdate` |

---

## 5. Stream events (`SDKMessage`)

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `stream.assistant` | `type: assistant` text blocks | Async | shipped | `stream_cursor_chat` | → SSE `delta` | A/C | |
| `stream.thinking` | `type: thinking` | Async | shipped | `stream_cursor_chat` | → SSE `delta` + `thinking: true` | A/C | |
| `stream.tool_call` | `type: tool_call` (`SDKToolUseMessage`) | Async | partial | `stream_cursor_chat` | Allowlist → `tool_start` / `tool_output` | **B** | Chat: `generateImage` only |
| `tool.generateImage` | Tool name `generateImage` | Async | shipped | `cursor_tool_call_chunks`, `publish_cursor_generated_image` | → `image_url` under `/api/generated-image/` | A/C+ | Unstable args/result; defensive path parse |
| `stream.system` | `type: system` | Async | gap | — | Ignored | n/a | |
| `stream.user` | `type: user` (`SDKUserMessageEvent`) | Async | gap | — | Ignored on stream | n/a | |
| `stream.status` | `type: status` | Async | gap | — | Ignored | C+ | Optional status line |
| `stream.task` | `type: task` | Async | gap | — | Ignored | B | |
| `stream.request` | `type: request` | Async | gap | — | Ignored | n/a | |
| `stream.error` | `type: error` on stream | Async | shipped | `stream_cursor_chat` | → SSE `event: error` | A/C | |

---

## 6. SendOptions and conversation mode

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `send.model_override` | Per-send `model` in options | Async | shipped | `agent.send(payload, {"model": model})` | Override on each send; sticky in SDK | A/C | Critical for resume |
| `send.mode_plan` | `mode: "plan"` | Async | gap | — | Default SDK agent mode in Chat | **B** | Plan-first workflows |
| `send.mode_agent` | `mode: "agent"` | Async | gap | — | Not set from Odysseus | **B** | Implements changes |
| `send.mcp_servers` | Inline MCP per send | Async | gap | — | — | **B** / Phase 3 | Replaces creation-time servers |
| `send.local_force` | `local.force=True` (expire stuck run) | Local | gap | — | — | Phase 2 | Cloud uses 409 instead |
| `send.idempotency_key` | Client idempotency key | Cloud | n/a | — | — | n/a | |
| `opts.model_params` | `ModelSelection.params` (e.g. thinking) | Both | gap | — | Model ID only in admin | Phase 2 | Discover via `models.list()` |

---

## 7. Images (input)

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `image.user_message` | `UserMessage(text, images=…)` | Async | shipped | `build_cursor_user_message` | Resume + first turn with attachments | A/C | |
| `image.from_file` | `SDKImage.from_file(path)` | Async | shipped | `_sdk_images_from_content` | Local file paths from attachments | A/C | |
| `image.from_data` | `SDKImage.from_data` / data URL | Async | shipped | `_sdk_images_from_content` | Base64 `data:image/…` blocks | A/C | |
| `image.from_url` | `SDKImage.url_image(url)` | Async | gap | — | Remote URLs not mapped | Phase 2 | Rare in Odysseus uploads |
| `image.chat_guard` | Chat accepts images on Cursor endpoint | Async | shipped | `chat_accepts_image_attachments` | Cursor uses SDKImage, not vision sidecar | A/C | Test: `test_cursor_chat_endpoint_accepts_images` |

---

## 8. Models API

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `models.rest_list` | `GET /v1/models` | REST | shipped | `list_cursor_model_entries` | Basic auth; id + displayName | A/C | |
| `models.picker_display` | `displayName` in model picker | REST | shipped | `normalize_cached_cursor_models`, `model_routes` | Legacy string lists upgraded | A/C | |
| `models.sdk_list` | `client.models.list()` | Async | gap | — | Uses REST only | n/a | REST sufficient |
| `models.variants` | Model variants / parameters from API | REST | gap | — | IDs only stored | Phase 2 | |

---

## 9. MCP

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `mcp.http_config` | `HttpMcpServerConfig` | Both | gap | — | Odysseus MCP admin separate | **B** / Phase 3 | OAuth via Cursor backend |
| `mcp.stdio_config` | `StdioMcpServerConfig` | Both | gap | — | — | **B** | Cloud passes env into VM |
| `mcp.creation_time` | MCP on `Agent.create` | Both | gap | — | — | **B** | |
| `mcp.workspace_file` | `.cursor/mcp.json` in cwd | Local | partial | — | Implicit via bridge cwd | **B** | Document for Plan B v1 |
| `mcp.odysseus_admin` | Map `McpServer` DB rows → SDK | Both | gap | — | Native agent uses DB MCP | Phase 3 | Plan B §8 |

---

## 10. Cloud-only SDK features

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `cloud.repos` | `CloudRepository`, `client.repositories.list()` | Cloud | n/a | — | — | wont-fix | |
| `cloud.auto_create_pr` | `auto_create_pr` on create | Cloud | n/a | — | — | wont-fix | |
| `cloud.env_vars` | Session `env_vars` on cloud create | Cloud | n/a | — | — | wont-fix | |
| `cloud.artifacts_list` | `agent.list_artifacts()` | Cloud | n/a | — | Local returns empty | wont-fix | |
| `cloud.artifacts_download` | `agent.download_artifact(path)` | Cloud | n/a | — | Local raises | wont-fix | |
| `cloud.agent_busy` | 409 when run in progress | Cloud | partial | — | Implicit single-send per session | Phase 2 | Serialize user sends |

---

## 11. REST-only (Cloud Agents API, not SDK adapter)

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `rest.agents_crud` | POST/GET/list/archive/delete agents | REST | n/a | — | SDK wraps; Odysseus uses SDK | wont-fix | |
| `rest.runs_crud` | Create/list/get/cancel runs | REST | partial | — | Cancel via SDK `run.cancel` only | Phase 3 | |
| `rest.stream_sse` | `GET …/runs/{id}/stream` | REST | gap | — | SDK `run.messages()` used instead | Phase 3 | 410 recovery path |
| `rest.stream_410` | `410 stream_expired` + retention header | REST | gap | — | No fallback poll | Phase 3 | Poll Get Run |
| `rest.webhooks` | Cloud agent webhooks | REST | n/a | — | — | wont-fix | |
| `rest.workers` | Worker tokens / fleet API | REST | n/a | — | — | wont-fix | |

---

## 12. Odysseus admin and routing

| ID | SDK capability | Surface | Status | Odysseus location | Behavior today | Plan | Notes |
|----|----------------|---------|--------|-------------------|----------------|------|-------|
| `ody.endpoint_preset` | `provider=cursor`, `cursor://local` | App | shipped | `model_routes`, admin UI | Workspace cwd in `provider_config` | A/C | |
| `ody.supports_tools_false` | Cursor endpoints disable Odysseus tools | App | shipped | `model_routes` | `supports_tools=False` | A/C | |
| `ody.chat_only_guard` | Agent/Compare/Research block | App | **blocked** | `chat_routes.py` ~886 | HTTP 400 clear error | **B** to unblock | |
| `ody.utility_exclude` | Utility resolver skips Cursor | App | shipped | `endpoint_resolver.py` | `exclude_cursor=True` | A/C | |
| `ody.vision_fallback_exclude` | Vision fallback skips Cursor | App | shipped | `endpoint_resolver.py` | Same | A/C | |
| `ody.task_http_guard` | No HTTP fallback to `cursor://` | App | shipped | `endpoint_resolver.py` | Background tasks can't POST cursor | A/C | |
| `ody.fallback_chain` | Chat fallback includes Cursor candidates | App | shipped | `stream_llm_with_fallback` | Works through cursor branch | A/C | |
| `ody.workspace_roots` | `CURSOR_ALLOWED_WORKSPACE_ROOTS` | App | shipped | `validate_cursor_cwd` | Path allowlist | A/C | |
| `ody.optional_install` | `requirements-cursor.txt` | App | shipped | `scripts/cloud-agent-install.sh` | Clear 503 if SDK missing | A/C | |
| `ody.shutdown` | Close bridges on app shutdown | App | shipped | `close_cursor_bridges` | Called from app lifecycle | A/C | |

---

## 13. Odysseus-native features (reverse map)

Features Odysseus **Agent mode** provides that a Cursor engine would **not** automatically replace. Plan B should document or inject as text prefix only.

| Feature | Native Odysseus | With Cursor SDK (today) | Plan B approach |
|---------|-----------------|-------------------------|-----------------|
| Built-in tools (`agent_tools.py`) | `stream_agent_loop` | Not used for Cursor Chat | Disable; use Cursor tools |
| MCP from admin DB | Wired in agent loop | Not mapped to SDK | `.cursor/mcp.json` or Phase 3 mapping |
| Skills injection | `skills_manager` | Not passed to SDK | Text prefix on `send()` |
| Memory / RAG tools | Agent tools + context | Not passed | Text prefix / read-only context |
| Compare / Research modes | `stream_agent_loop` | Cursor blocked | Keep blocked or wont-fix |
| Native image gen (`do_generate_image`) | Separate path for DALL·E etc. | Unrelated to Cursor `generateImage` | C+ maps Cursor tool separately |
| Image MCP (`generate_image` tool) | Agent MCP server | Cursor has own `generateImage` | Different code paths |

---

## Maintenance

- **After Plan C+:** Update rows `stream.tool_call`, `tool.generateImage`, and any new asset-serving helpers to **shipped**.
- **After Plan B:** Update `send.mode_*`, `ody.chat_only_guard`, and tool rows to **shipped** or **partial**.
- **Re-verify** against Nia `71741e4c` when `cursor-sdk` is upgraded beyond `0.1.6`.

**Tests to run after matrix-affecting code changes:**

```bash
pytest tests/test_cursor_adapter.py tests/test_cursor_plan_c.py tests/test_model_routes.py -q
```
