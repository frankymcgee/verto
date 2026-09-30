"""GPT-Live transport; task rules and tool execution stay in the shared JHA workflow."""
from __future__ import annotations

import copy

import frappe
from frappe import _


def build_live_session(*, config: dict, conversation_style: str, backend_instructions: str,
                       tools: list[dict], work_summary: str, progress: dict) -> dict:
    # Responses defaults optional fields to required in strict mode. Preserve the
    # existing JHA schemas, where the crew can supply fields incrementally.
    response_tools = copy.deepcopy(tools)
    for tool in response_tools:
        tool["strict"] = False

    live_instructions = f"""
You are PERI, the voice facilitator for a crew developing a draft Job Hazard Analysis.
Speak in English using the selected voice. {conversation_style}
Work Summary: {work_summary}
Saved stage: {progress['stage']}; current step: {progress['current_step_sequence'] or 'None'} {progress['current_step_activity']}.
Resume the saved stage. Ask one focused question at a time and listen to the crew's answer.
Backchannel policy: Follow the configured acknowledgement style. Brief listening sounds must not compete with the crew.
Interruption policy: Stop speaking when the crew interrupts and listen. Delegate corrections to task state separately.
Delegation policy:
Backend tools: Read the saved JHA, record confirmed steps/hazards/controls/participants, find relevant incident lessons, check completeness, and move a complete draft to human review.
Delegate to the backend when: The crew supplies a JHA answer, correction, step decision, hazard/control discussion, critical-risk or incident question, participant detail, or completeness/review request.
Do not delegate to the backend when: The crew greets you, asks you to repeat a still-current verified result, or needs a brief clarification before you understand their answer.
The backend owns the ordered workflow and current saved state. Use its next question and verified results to continue the discussion. Do not advance or invent a saved change yourself.
Never claim a change succeeded before the backend confirms it. When the backend reports a failure, explain it briefly and ask only for the missing detail.
For historical incidents, say only the source facts and actions supplied by the backend. Separate those facts from proposed controls, ask the crew to confirm applicability and delegate that confirmation before a control is recorded.
Never state the job is safe, approved or authorised. Never sign, acknowledge or approve for a person. Human review and sign-on are still required.
Do not repeat successful writes aloud when silent-tool-success is enabled. Continue with the next missing question from the backend. Acknowledge a correction without retaining its superseded value.
""".strip()

    responses = {
        "model": config["live_backend_model"],
        "instructions": backend_instructions + "\n\nGPT-Live is the spoken interface. Return verified results and the next concise crew question. Follow the same ordered facilitation flow. Use get_current_jha_state before acting whenever current saved state may have changed. Apply the crew's latest corrections; confirm applicability before recording suggested incident-informed controls. Do not treat transcript fragments as separate complete answers.",
        "tools": response_tools,
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "reasoning": {"effort": config["live_reasoning_effort"]},
    }
    voice = {"id": config["live_custom_voice_id"]} if config.get("live_custom_voice_id") else config["live_voice"]
    return {
        "model": config["live_model"],
        "instructions": live_instructions,
        "audio": {"output": {"voice": voice}},
        "client": {"data_channel": {
            "allowed_client_events": ["session.instructions.append", "session.close", "response.item.create", "response.create"],
            "allowed_server_events": "all",
        }},
        "delegation": {"type": "responses", "responses": responses},
        "store": False,
    }


def create_live_call(*, client, sdp: str, session: dict) -> dict:
    # Session creation incurs duration charges. Avoid SDK retries after an
    # ambiguous failure, even when Raven configures a retrying default client.
    client = client.with_options(max_retries=0)
    live = getattr(client, "live", None)
    if live is not None and callable(getattr(live, "create", None)):
        response = live.create(session=session, transport={"type": "webrtc", "sdp": sdp})
        payload = response if isinstance(response, dict) else response.model_dump()
    elif callable(getattr(client, "post", None)):
        # Raven may pin an SDK predating the typed Live resource. Its public HTTP
        # client still applies the existing API key, base URL and project headers.
        payload = client.post("/live/sessions", cast_to=dict, body={
            "session": session, "transport": {"type": "webrtc", "sdp": sdp},
        })
    else:
        frappe.throw(_("Update Raven/OpenAI dependencies to enable GPT Live WebRTC sessions."), frappe.ValidationError)

    answer = str((payload.get("transport") or {}).get("sdp") or "")
    reference = str((payload.get("session") or {}).get("id") or "")
    if not answer.startswith("v=0") or not reference:
        frappe.throw(_("OpenAI did not return a valid GPT Live session and WebRTC SDP answer."), frappe.ValidationError)
    return {"sdp": answer, "model": session["model"], "session_reference": reference}
