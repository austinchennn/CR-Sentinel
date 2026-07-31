import pytest

from patrol_agent import sql_literals


def test_quote_string_escapes_single_quotes():
    assert sql_literals.quote_string("1' OR '1'='1") == "'1'' OR ''1''=''1'"


def test_quote_string_plain_value():
    assert sql_literals.quote_string("203.0.113.5") == "'203.0.113.5'"


def test_quote_vector_formats_floats():
    literal = sql_literals.quote_vector([0.1, -0.2, 1.0])
    assert literal == "'[0.1, -0.2, 1.0]'"


def test_quote_vector_rejects_empty():
    with pytest.raises(ValueError):
        sql_literals.quote_vector([])


def test_quote_int_coerces():
    assert sql_literals.quote_int("5") == "5"
