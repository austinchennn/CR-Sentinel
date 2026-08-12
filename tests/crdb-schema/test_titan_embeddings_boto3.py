"""Covers the `client is None` lazy-boto3-import branch of embed_text(),
which services/crdb-schema/tests/test_titan_embeddings.py doesn't exercise
(it always injects a fake client)."""
from crdb_schema import titan_embeddings


def test_embed_text_builds_its_own_bedrock_client_when_none_given(fake_boto3):
    result = titan_embeddings.embed_text("union select")

    assert result == [0.0] * 1024
    assert fake_boto3.calls == ["bedrock-runtime"]
    assert fake_boto3.client.invoke_model_calls[0]["modelId"] == titan_embeddings.MODEL_ID
