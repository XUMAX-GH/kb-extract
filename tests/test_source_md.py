from kb_extract.source_md import strip_images


def test_strip_images_removes_markdown_images_and_counts():
    md = (
        "# Title\n\n"
        "Intro text.\n\n"
        "![company logo](assets/logo.png)\n\n"
        "Body with inline ![x](data:image/png;base64,AAAA) image.\n\n"
        '<img src="banner.png" alt="b"/>\n'
    )
    out, count = strip_images(md)
    assert "logo.png" not in out
    assert "base64" not in out
    assert "<img" not in out
    assert "# Title" in out
    assert "Intro text." in out
    assert count == 3
