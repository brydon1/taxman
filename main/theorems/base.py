from typing import Iterator

from main.database import Database

# Theorem registries.  Each theorem module imports one of these dicts and
# inserts its handler on import, e.g.:
#   ABSTRACT_THEOREMS['STOCKHOLDER'] = stockholder_fn
ABSTRACT_THEOREMS: dict[str, callable] = {}
EXPAND_THEOREMS: dict[str, callable] = {}


def goal_abstract(db: Database, concept: str, *args) -> Iterator[dict]:
    """Query for *concept* with pattern *args*.

    Tries a direct DB lookup first.  Falls back to a registered abstract
    theorem if the DB returns nothing.
    """
    results = list(db.query(concept, *args))
    if results:
        yield from results
        return

    if concept in ABSTRACT_THEOREMS:
        yield from ABSTRACT_THEOREMS[concept](db, *args)


def assert_expand(db: Database, concept: str, *args) -> None:
    """Assert *concept* via its registered expand theorem, or directly.

    If no theorem is registered the proposition is stored as-is.
    """
    if concept in EXPAND_THEOREMS:
        EXPAND_THEOREMS[concept](db, *args)
    else:
        db.assert_(concept, *args)
