import hashlib
import shutil
from pathlib import Path

from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.orchestrator import run


def _hash_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.sqlite":
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_h8_byte_identical_double_extract(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"reproducible")
    reg = Registry()
    reg.register(NoopAdapter())

    run(project, registry=reg, force=True)
    first = _hash_tree(project / "kb")

    # Wipe and re-run.
    shutil.rmtree(project / "kb")
    run(project, registry=reg, force=True)
    second = _hash_tree(project / "kb")

    assert first == second, "outputs not byte-identical between runs (H8 violation)"
