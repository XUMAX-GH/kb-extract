import zipfile
from pathlib import Path

import pytest

from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.adapters.zip import ZipAdapter
from kb_extract.hardness import assert_invariants


def _make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


@pytest.mark.disable_socket
def test_zip_adapter_returns_aggregate_section(tmp_path):
    src = _make_zip(tmp_path / "a.zip", {"inner.noop": b"x"})
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    reg = Registry()
    reg.register(NoopAdapter())
    a = ZipAdapter(child_registry=reg)
    result = a.extract(src, out_dir)
    assert result.index.title == src.stem
    # One child for inner.noop
    assert len(result.index.children) == 1
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)


@pytest.mark.disable_socket
def test_zip_adapter_marks_encrypted_skipped(tmp_path):
    src = tmp_path / "enc.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("x.noop", b"data")
        # Mark all entries as encrypted by setting flag bit 0 manually
        for info in zf.filelist:
            info.flag_bits |= 0x1
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    reg = Registry()
    reg.register(NoopAdapter())
    a = ZipAdapter(child_registry=reg)
    result = a.extract(src, out_dir)
    assert any(w.startswith("zip.encrypted:") for w in result.meta.warnings)
