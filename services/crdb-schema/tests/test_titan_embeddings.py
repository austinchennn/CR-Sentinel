import json

import pytest

from crdb_schema import titan_embeddings


class FakeBody:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()


class FakeBedrockClient:
    def __init__(self, embedding):
        self._embedding = embedding
        self.calls = []

    def invoke_model(self, modelId, body, contentType, accept):
        self.calls.append({"modelId": modelId, "body": json.loads(body), "contentType": contentType, "accept": accept})
        return {"body": FakeBody({"embedding": self._embedding})}


def test_embed_text_sends_titan_request_shape():
    client = FakeBedrockClient(embedding=[0.1] * 1024)

    result = titan_embeddings.embed_text("union select", client=client)

    assert result == [0.1] * 1024
    call = client.calls[0]
    assert call["modelId"] == "amazon.titan-embed-text-v2:0"
    assert call["body"] == {"inputText": "union select", "dimensions": 1024, "normalize": True}


def test_embed_text_respects_custom_dimensions():
    client = FakeBedrockClient(embedding=[0.2] * 512)

    result = titan_embeddings.embed_text("x", client=client, dimensions=512)

    assert len(result) == 512
    assert client.calls[0]["body"]["dimensions"] == 512


def test_embed_text_rejects_dimension_mismatch():
    client = FakeBedrockClient(embedding=[0.1] * 512)

    with pytest.raises(ValueError):
        titan_embeddings.embed_text("x", client=client)
