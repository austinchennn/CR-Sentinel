from attack_simulator.scenarios import chained_intrusion, idor_enumeration, obfuscated_sqli, slow_bruteforce


def _no_sleep(seconds):
    pass


def test_obfuscated_sqli_sends_all_payload_variants_to_profile(fake_client):
    client = fake_client

    result = obfuscated_sqli.run(client, sleep_fn=_no_sleep)

    assert result.requests_sent == len(obfuscated_sqli.PAYLOADS)
    assert len(client.calls) == len(obfuscated_sqli.PAYLOADS)
    for method, path, params in client.calls:
        assert method == "GET"
        assert path == "/profile"
        assert params["id"] in obfuscated_sqli.PAYLOADS
    assert result.expected_risk_level == "high"
    assert result.expected_attack_type == "sqli"


def test_slow_bruteforce_tries_every_password_for_one_username(fake_client):
    client = fake_client

    result = slow_bruteforce.run(client, sleep_fn=_no_sleep, delay_seconds=0)

    assert result.requests_sent == len(slow_bruteforce.GUESSED_PASSWORDS)
    assert len(client.calls) == len(slow_bruteforce.GUESSED_PASSWORDS)
    for method, path, body in client.calls:
        assert method == "POST"
        assert path == "/login"
        assert body["username"] == slow_bruteforce.USERNAME
        assert body["password"] in slow_bruteforce.GUESSED_PASSWORDS
    assert result.expected_attack_type == "bruteforce"


def test_idor_enumeration_walks_sequential_ids(fake_client):
    client = fake_client

    result = idor_enumeration.run(client, sleep_fn=_no_sleep)

    assert result.requests_sent == len(idor_enumeration.USER_IDS)
    ids_requested = [params["id"] for _, _, params in client.calls]
    assert ids_requested == idor_enumeration.USER_IDS
    assert result.expected_attack_type == "idor"


def test_chained_intrusion_runs_all_four_steps_in_order(fake_client):
    client = fake_client

    result = chained_intrusion.run(client, sleep_fn=_no_sleep)

    methods_and_paths = [(method, path) for method, path, _ in client.calls]
    assert methods_and_paths[0] == ("GET", "/admin")
    assert methods_and_paths[1] == ("POST", "/login")
    assert methods_and_paths[2] == ("GET", "/profile")
    assert methods_and_paths[3] == ("GET", "/profile")
    assert methods_and_paths[4] == ("GET", "/admin")
    assert result.requests_sent == len(client.calls) == 5
    assert result.expected_attack_type == "chained_intrusion"
