from pathlib import Path


def test_skill_md_declares_trigger_phrases():
    p = Path(__file__).resolve().parents[1] / "skills" / "kb-extract" / "SKILL.md"
    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "trigger" in body.lower()
    assert "kb extract" in body
    assert "extract this folder" in body.lower() or "extract folder" in body.lower()


def test_skill_scripts_never_import_kb_extract():
    """Spec sec.8.2: scripts must shell out to `kb` CLI, never import the package."""
    skill_dir = Path(__file__).resolve().parents[1] / "skills" / "kb-extract" / "scripts"
    for script in skill_dir.rglob("*.ps1"):
        assert "import kb_extract" not in script.read_text(encoding="utf-8"), script
        assert "kb_extract." not in script.read_text(encoding="utf-8"), script
    for script in skill_dir.rglob("*.sh"):
        body = script.read_text(encoding="utf-8")
        assert "import kb_extract" not in body, script


def test_skill_extract_scripts_exist():
    skill_dir = Path(__file__).resolve().parents[1] / "skills" / "kb-extract" / "scripts"
    assert (skill_dir / "extract.ps1").exists()
    assert (skill_dir / "extract.sh").exists()


def test_skill_extract_scripts_call_kb_adapters_then_extract():
    skill_dir = Path(__file__).resolve().parents[1] / "skills" / "kb-extract" / "scripts"
    for script in (skill_dir / "extract.ps1", skill_dir / "extract.sh"):
        body = script.read_text(encoding="utf-8")
        # Must check `kb adapters` first per SKILL.md contract.
        assert "kb adapters" in body
        assert "kb extract" in body
        assert "--json" in body


def test_skill_verify_scripts_exist():
    skill_dir = Path(__file__).resolve().parents[1] / "skills" / "kb-extract" / "scripts"
    assert (skill_dir / "verify.ps1").exists()
    assert (skill_dir / "verify.sh").exists()


def test_vscode_tasks_example_exists():
    p = Path(__file__).resolve().parents[1] / ".vscode" / "tasks.json.example"
    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "KB: Extract" in body
    assert "KB: Verify" in body


def test_plugin_manifest_exists_and_valid():
    """Plugin can be installed as a Copilot CLI marketplace entry."""
    import json
    plugin_root = Path(__file__).resolve().parents[1]
    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    marketplace_json = plugin_root / ".claude-plugin" / "marketplace.json"
    assert plugin_json.exists(), "plugin.json missing"
    assert marketplace_json.exists(), "marketplace.json missing"
    pj = json.loads(plugin_json.read_text(encoding="utf-8"))
    assert pj["name"] == "kb-extract"
    assert pj["version"]
    mj = json.loads(marketplace_json.read_text(encoding="utf-8"))
    assert any(p["name"] == "kb-extract" for p in mj["plugins"])
