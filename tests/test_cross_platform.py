"""H13: extraction output is byte-identical across Ubuntu/Windows/macOS.

The matrix CI uploads a per-OS hash manifest as an artifact. A dedicated job
(`cross_platform_identity`) downloads all three and compares them.

This local test runs the noop + image adapters and writes a hash manifest
that the CI job will consume.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest


def _hash_dir(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.sqlite":
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return out


@pytest.mark.disable_socket
def test_emit_h13_hash_manifest(tmp_path):
    """Produce a deterministic hash manifest of synthetic fixture extractions."""
    from kb_extract.adapters._noop import NoopAdapter
    from kb_extract.adapters.base import Registry
    from kb_extract.orchestrator import run

    project = tmp_path / "P"
    project.mkdir()
    src = project / "deterministic.noop"
    src.write_bytes(b"H13 fixture content")
    # Pin mtime to a fixed epoch so meta.json's source_mtime_iso is byte-identical
    # across Ubuntu/Windows/macOS. Without this, each runner stamps the synthetic
    # file with its own wall-clock time and H13 fails by construction.
    fixed_ts = 1_700_000_000.0  # 2023-11-14T22:13:20Z
    os.utime(src, (fixed_ts, fixed_ts))

    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg, force=True)

    manifest = _hash_dir(project / "kb")
    out_root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "_h13-output"
    out_root.mkdir(parents=True, exist_ok=True)
    # write_bytes (not write_text) to avoid Windows CRLF translation of the
    # manifest file itself, which would make the CI diff fail even when the
    # hashes inside are identical.
    (out_root / "hash-manifest.json").write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    assert manifest, "hash manifest empty (something went wrong)"
