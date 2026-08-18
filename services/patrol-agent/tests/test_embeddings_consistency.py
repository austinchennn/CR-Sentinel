"""Guards against `patrol_agent/embeddings.py` and
`crdb_schema/titan_embeddings.py` silently drifting apart.

Both modules are deliberate byte-for-byte copies of each other, not a
shared import -- each `services/*` directory deploys as its own
independent Lambda (see both modules' docstrings), so there's no shared
package to import from without adding a Lambda layer or a published
internal package. If MODEL_ID/EMBEDDING_DIMENSIONS ever diverge between
the two, query-time embeddings (this service) and seed-time embeddings
(crdb-schema) stop coming from the same vector space and semantic recall
quality degrades silently -- nothing else would catch that. See
docs/03-open-issues.md for the tracked risk this closes the loop on.
"""
import sys
from pathlib import Path

from patrol_agent import embeddings as patrol_embeddings

_CRDB_SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "crdb-schema"
sys.path.insert(0, str(_CRDB_SCHEMA_ROOT))

from crdb_schema import titan_embeddings as crdb_embeddings  # noqa: E402


def test_model_id_matches_crdb_schema_titan_embeddings():
    assert patrol_embeddings.MODEL_ID == crdb_embeddings.MODEL_ID


def test_embedding_dimensions_matches_crdb_schema_titan_embeddings():
    assert patrol_embeddings.EMBEDDING_DIMENSIONS == crdb_embeddings.EMBEDDING_DIMENSIONS
