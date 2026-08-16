"""Structural (`typing.Protocol`) type for `seed_attack_signatures.seed`'s
`embed_fn` dependency-injection seam -- production callers pass
`titan_embeddings.embed_text`, tests pass a fake, deterministic embedder
(see tests/test_seed_attack_signatures.py). Documentation/type-checker aid
only; nothing here changes behavior.
"""
from typing import Callable

EmbedFn = Callable[[str], list]
