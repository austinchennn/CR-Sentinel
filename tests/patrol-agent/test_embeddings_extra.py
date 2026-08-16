"""Covers the `client is None` lazy-boto3-import branch of
patrol_agent.embeddings.embed_text(), which
services/patrol-agent/tests/test_embeddings.py doesn't exercise (it always
injects a fake client)."""
from patrol_agent import embeddings


def test_embed_text_builds_its_own_bedrock_client_when_none_given(fake_boto3):
    result = embeddings.embed_text("union select")

    assert result == [0.0] * 1024
    assert fake_boto3.calls == ["bedrock-runtime"]
    assert fake_boto3.client.invoke_model_calls[0]["modelId"] == embeddings.MODEL_ID
