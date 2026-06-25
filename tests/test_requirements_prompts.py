import json

from kb_extract.wiki.requirements.prompts import (
    build_system_prompt,
    compose_messages,
)


def test_system_prompt_combines_base_and_p2():
    sp = build_system_prompt()
    # From base_system_rules.md
    assert "OUTPUT SCHEMA" in sp
    # Layer separator
    assert "---" in sp
    # From p2_rules.md (P2 precision variant)
    assert "P2" in sp


def test_compose_messages_embeds_anchor_as_evidence_id():
    msgs = compose_messages(
        anchor="sec-0007",
        section_title="3.2.1 Hinge Stiffness",
        section_body="Stiffness must be >= 5 N/mm.",
    )
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "sec-0007" in msgs[1]["content"]
    assert "Stiffness must be" in msgs[1]["content"]
    body = msgs[1]["content"]
    # Evidence JSON is wrapped in a ```json ... ``` code fence in the template.
    fence_start = body.index("```json\n") + len("```json\n")
    fence_end = body.index("\n```", fence_start)
    blocks = json.loads(body[fence_start:fence_end])
    assert blocks[0]["id"] == "sec-0007"


def test_deterministic():
    a = compose_messages(anchor="sec-0001",
                         section_title="Voltage", section_body="3.3V")
    b = compose_messages(anchor="sec-0001",
                         section_title="Voltage", section_body="3.3V")
    assert a == b
