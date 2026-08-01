import json

import pytest

from patrol_agent import embeddings


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
        self.calls.append({"modelId": modelId, "body": json.loads(body)})
        return {"body": FakeBody({"embedding": self._embedding})}


def test_embed_text_sends_titan_request_shape():
    client = FakeBedrockClient(embedding=[0.1] * 1024)

    result = embeddings.embed_text("union select", client=client)

    assert result == [0.1] * 1024
    call = client.calls[0]
    assert call["modelId"] == "amazon.titan-embed-text-v2:0"
    assert call["body"] == {"inputText": "union select", "dimensions": 1024, "normalize": True}


def test_embed_text_rejects_dimension_mismatch():
    client = FakeBedrockClient(embedding=[0.1] * 512)

    with pytest.raises(ValueError):
        embeddings.embed_text("x", client=client)
