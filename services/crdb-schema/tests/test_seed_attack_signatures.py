from crdb_schema.seed_attack_signatures import seed


def fake_embed(text):
    return [float(len(text))]


def test_seed_upserts_every_signature_and_commits_once(fake_conn):
    signatures = [
        {"category": "sqli", "description": "desc one", "severity": "high"},
        {"category": "xss", "description": "desc two", "severity": "medium"},
    ]

    count = seed(fake_conn, fake_embed, signatures=signatures)

    assert count == 2
    assert len(fake_conn.executed) == 2
    statement, params = fake_conn.executed[0]
    assert "ON CONFLICT (category, description) DO UPDATE" in statement
    assert params == ("sqli", "desc one", "high", [8.0])
    assert fake_conn.committed == 1


def test_seed_embeds_the_description_text_of_every_signature(fake_conn):
    calls = []

    def counting_embed(text):
        calls.append(text)
        return [1.0]

    seed(
        fake_conn,
        counting_embed,
        signatures=[
            {"category": "sqli", "description": "a", "severity": "high"},
            {"category": "sqli", "description": "b", "severity": "high"},
        ],
    )

    assert calls == ["a", "b"]


def test_seed_defaults_to_the_real_seed_list(fake_conn):
    from crdb_schema.attack_signature_seed_data import SEED_ATTACK_SIGNATURES

    count = seed(fake_conn, fake_embed)

    assert count == len(SEED_ATTACK_SIGNATURES)
    assert len(fake_conn.executed) == len(SEED_ATTACK_SIGNATURES)
