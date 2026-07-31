from crdb_schema.attack_signature_seed_data import SEED_ATTACK_SIGNATURES

REQUIRED_CATEGORIES = {"sqli", "xss", "idor", "bruteforce", "phishing"}


def test_covers_all_five_required_categories():
    categories = {s["category"] for s in SEED_ATTACK_SIGNATURES}
    assert REQUIRED_CATEGORIES <= categories


def test_each_required_category_has_at_least_three_entries():
    counts = {}
    for s in SEED_ATTACK_SIGNATURES:
        counts[s["category"]] = counts.get(s["category"], 0) + 1
    for category in REQUIRED_CATEGORIES:
        assert counts.get(category, 0) >= 3, f"{category} has only {counts.get(category, 0)} seed entries"


def test_descriptions_are_unique_and_substantive():
    descriptions = [s["description"] for s in SEED_ATTACK_SIGNATURES]
    assert len(descriptions) == len(set(descriptions))
    assert all(len(d) >= 20 for d in descriptions)


def test_every_entry_has_a_known_severity():
    valid = {"low", "medium", "high"}
    assert all(s["severity"] in valid for s in SEED_ATTACK_SIGNATURES)


def test_every_entry_has_exactly_the_expected_keys():
    for s in SEED_ATTACK_SIGNATURES:
        assert set(s.keys()) == {"category", "severity", "description"}
