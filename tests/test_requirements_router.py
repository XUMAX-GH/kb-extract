from kb_extract.wiki.requirements.router import FALLBACK_DOMAIN, route_heading


def test_keyword_routes_mechanical():
    r = route_heading("Retractable Hinge Stiffness and Deflection")
    assert r.domain == "mechanical"
    assert r.method == "keyword"


def test_section_pattern_takes_priority():
    # "8." -> dfx-manufacturing via section_patterns even with generic words
    r = route_heading("8. Design for Excellence")
    assert r.domain == "dfx-manufacturing"
    assert r.method == "section_pattern"


def test_no_match_falls_back():
    r = route_heading("Acknowledgements and Greetings")
    assert r.domain == FALLBACK_DOMAIN
    assert r.method == "fallback"


def test_keyboard_input_keywords():
    r = route_heading("Touchpad force to fire and snap ratio")
    assert r.domain == "keyboard-input"


def test_deterministic_repeat():
    a = route_heading("Power Management and Battery Life")
    b = route_heading("Power Management and Battery Life")
    assert a == b
    assert a.domain == "power-battery"


def test_exact_section_pattern_with_trailing_dot():
    # "3.3" exact pattern (repair-serviceability) must match with or without a trailing dot,
    # and must not be stolen by a generic keyword domain.
    assert route_heading("3.3 Serviceability").domain == "repair-serviceability"
    assert route_heading("3.3. Serviceability").domain == "repair-serviceability"


def test_prefix_section_pattern_still_matches():
    assert route_heading("8. Design for Excellence").domain == "dfx-manufacturing"
    assert route_heading("10. Compliance").domain == "compliance-safety"
