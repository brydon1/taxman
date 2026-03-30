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
