"""Thin wrapper around Bedrock's Titan Text Embeddings V2 model.

Kept separate from seed_attack_signatures.py so PatrolAgentLambda (PRD-04)
can import just this to embed query text/log snippets at inference time,
using the same model as seeding -- docs/01-architecture.md is explicit
that query-time and seed-time embeddings must come from one model or the
vector space drifts and recall quality degrades.

`boto3` is imported lazily inside `embed_text`, not at module load time,
so this module -- and anything that only needs EMBEDDING_DIMENSIONS/MODEL_ID
-- stays importable without the dependency installed. Same convention as
demo_target_app/db.py and patrol_agent/write_client.py.
"""
import json

EMBEDDING_DIMENSIONS = 1024
MODEL_ID = "amazon.titan-embed-text-v2:0"


def embed_text(text, client=None, dimensions=EMBEDDING_DIMENSIONS):
    if client is None:
        import boto3

        client = boto3.client("bedrock-runtime")

    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": dimensions, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(response["body"].read())
    embedding = payload["embedding"]
    if len(embedding) != dimensions:
        raise ValueError(f"expected a {dimensions}-dim embedding, got {len(embedding)}")
    return embedding
