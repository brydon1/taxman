"""
TAXMAN Symbols — fresh symbol generation and timeline management.

gen() implements the "nominalization convention": whenever TAXMAN needs to
treat a concept as an object (so further predicates can hang off it), it
creates a fresh unique symbol and asserts two propositions:

    s1 = gen()                       # → 'PHE1'
    db.assert_('ISSUE', 'NEW-JERSEY', s1)
    db.assert_('STOCK', s1)

The same pattern applies to ownership interests — Phellis doesn't own a
stock class directly; he owns a *piece-of* a stock class:

    p1 = gen()                       # → 'PHE2'
    db.assert_('PIECE-OF', p1, s1)
    db.assert_('NSHARES', p1, 100)
    db.assert_('OWN', 'PHELLIS', p1)

Timeline manages the sequence of discrete state tokens (T0, T1, T2, ...).
Each event that changes ownership advances the timeline, and the new token
is appended to the affected propositions so the DB preserves all states.
"""

_counter = 0


def gen(prefix: str = 'PHE') -> str:
    """Return a fresh unique symbol, e.g. 'PHE1', 'PHE2', ..."""
    global _counter
    _counter += 1
    return f'{prefix}{_counter}'


def reset_gen() -> None:
    """Reset the symbol counter to zero. Intended for test isolation only."""
    global _counter
    _counter = 0


class Timeline:
    """Manages discrete state tokens T0, T1, T2, ..."""

    def __init__(self):
        self._states: list[str] = ['T0']

    def current(self) -> str:
        return self._states[-1]

    def advance(self) -> str:
        n = len(self._states)
        t = f'T{n}'
        self._states.append(t)
        return t

    def all_states(self) -> list[str]:
        return list(self._states)
