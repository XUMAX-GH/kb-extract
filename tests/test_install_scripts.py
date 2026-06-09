from pathlib import Path


def test_install_ps1_exists_and_has_expected_steps():
    p = Path(__file__).resolve().parents[1] / "install.ps1"
    assert p.exists(), "install.ps1 missing"
    body = p.read_text(encoding="utf-8")
    for needle in ("uv venv", "uv pip install", "kb-extract", "DOCLING"):
        assert needle in body, f"install.ps1 missing reference to {needle!r}"


def test_install_sh_exists_and_has_expected_steps():
    p = Path(__file__).resolve().parents[1] / "install.sh"
    assert p.exists(), "install.sh missing"
    body = p.read_text(encoding="utf-8")
    for needle in ("uv venv", "uv pip install", "kb-extract"):
        assert needle in body


def test_uninstall_scripts_exist():
    repo = Path(__file__).resolve().parents[1]
    assert (repo / "uninstall.ps1").exists()
    assert (repo / "uninstall.sh").exists()
