from pathlib import Path

import pytest

from kb_extract.adapters.base import (
    Extractor,
    Registry,
    get_default_registry,
    register,
)


class _Dummy:
    name = "dummy"
    version = "0.1"
    extensions = (".dum",)

    def extract(self, src: Path, out_dir_tmp: Path):
        raise NotImplementedError


def test_register_and_pick_by_extension(tmp_path):
    r = Registry()
    r.register(_Dummy())
    fake = tmp_path / "x.dum"
    fake.write_bytes(b"x")
    picked = r.pick(fake)
    assert picked is not None
    assert picked.name == "dummy"


def test_pick_returns_none_for_unknown_extension(tmp_path):
    r = Registry()
    fake = tmp_path / "x.unknown"
    fake.write_bytes(b"x")
    assert r.pick(fake) is None


def test_pick_case_insensitive_extension(tmp_path):
    r = Registry()
    r.register(_Dummy())
    fake = tmp_path / "x.DUM"
    fake.write_bytes(b"x")
    assert r.pick(fake) is not None


def test_double_register_same_extension_raises():
    r = Registry()
    r.register(_Dummy())
    with pytest.raises(ValueError):
        r.register(_Dummy())


def test_register_decorator_adds_to_default_registry():
    @register
    class _AnotherDummy:
        name = "another"
        version = "0.1"
        extensions = (".another",)

        def extract(self, src, out_dir_tmp):
            raise NotImplementedError

    default = get_default_registry()
    names = [a.name for a in default.all()]
    assert "another" in names


def test_extractor_protocol_runtime_checkable():
    assert isinstance(_Dummy(), Extractor)
