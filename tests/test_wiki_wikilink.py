from kb_extract.wiki.wikilink import to_wikilink


def test_to_wikilink_with_label():
    assert to_wikilink("mechanical/_index", "MECHANICAL") == "[[mechanical/_index|MECHANICAL]]"


def test_to_wikilink_label_equals_target_omits_pipe():
    assert to_wikilink("hinge-torque", "hinge-torque") == "[[hinge-torque]]"


def test_to_wikilink_strips_md_extension():
    assert to_wikilink("hinge-torque.md", "Hinge") == "[[hinge-torque|Hinge]]"
