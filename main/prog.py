from typing import Iterator

from main.database import Database


def apply_bindings(args: tuple, bindings: dict) -> tuple:
    """Replace ?VAR slots with their bound value; leave ground values alone.

    Anonymous variable '?' has an empty name after stripping '?', so
    bindings.get('', '?') returns '?' when '' is absent — it stays anonymous
    and db.query will treat it as a wildcard.
    """
    return tuple(
        bindings.get(a[1:], a) if isinstance(a, str) and a.startswith('?') and len(a) > 1 else a
        for a in args
    )


def prog(
    db: Database,
    goals: list[tuple],
    bindings: dict | None = None,
) -> Iterator[dict]:
    """Yield each complete binding dict that satisfies all goals in sequence.

    ``goals`` is a list of ``(predicate, arg1, arg2, ...)`` tuples.
    Backtracking is implicit: when a later goal finds no matches the generator
    simply exhausts and the caller continues with the next match from an
    earlier goal.
    """
    if bindings is None:
        bindings = {}
    if not goals:
        yield dict(bindings)
        return

    pred, *args = goals[0]
    resolved_args = apply_bindings(tuple(args), bindings)

    for match in db.query(pred, *resolved_args):
        # Guard: skip if this match would rebind an already-bound variable to a
        # different value.  (apply_bindings substitutes known bindings first, so
        # this fires only for variables that appear in multiple goals and were
        # *not* yet bound at the time the earlier goal ran.)
        conflict = any(
            k in bindings and bindings[k] != v
            for k, v in match.items()
        )
        if conflict:
            continue
        merged = {**bindings, **match}
        yield from prog(db, goals[1:], merged)
