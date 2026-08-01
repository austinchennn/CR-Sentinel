"""Query-time Titan embedding wrapper for PatrolAgentLambda (PRD-04).

This is a deliberate copy of
`services/crdb-schema/crdb_schema/titan_embeddings.py`'s `embed_text`, not
a cross-service import: each directory under `services/` is packaged and
deployed as its own independent Lambda (see each service's `template.yaml`
`CodeUri: .`), the same reason `demo_target_app/db.py` and
`patrol_agent/write_client.py` each own their DB connection code instead
of sharing a package. MODEL_ID and EMBEDDING_DIMENSIONS must stay
identical to `crdb_schema.titan_embeddings` -- docs/01-architecture.md is
explicit that seed-time and query-time embeddings need to come from the
same model or vector recall quality degrades.

`boto3` is imported lazily inside `embed_text`, matching every other
lazy-import module in this package, so callers that supply a fake client
in tests never need the dependency installed.
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
