"""
Tests for main/symbols.py — symbol generation and Timeline (Layer 2a).
"""
import pytest
from main.symbols import gen, reset_gen, Timeline


@pytest.fixture(autouse=True)
def fresh_counter():
    """Reset the global gen() counter before every test."""
    reset_gen()
    yield
    reset_gen()


# ---------------------------------------------------------------------------
# gen()
# ---------------------------------------------------------------------------

class TestGen:
    def test_first_call_returns_phe1(self):
        assert gen() == 'PHE1'

    def test_increments_on_each_call(self):
        assert gen() == 'PHE1'
        assert gen() == 'PHE2'
        assert gen() == 'PHE3'

    def test_custom_prefix(self):
        assert gen('S') == 'S1'
        assert gen('S') == 'S2'

    # TODO should mixed prefixes share a counter?
    def test_mixed_prefixes_share_counter(self):
        # Counter is global, not per-prefix
        first = gen('A')
        second = gen('B')
        assert first == 'A1'
        assert second == 'B2'

    def test_generated_symbols_are_unique(self):
        symbols = [gen() for _ in range(10)]
        assert len(set(symbols)) == 10


# ---------------------------------------------------------------------------
# reset_gen()
# ---------------------------------------------------------------------------

class TestResetGen:
    def test_reset_restarts_counter(self):
        gen()
        gen()
        reset_gen()
        assert gen() == 'PHE1'

    def test_double_reset_is_idempotent(self):
        reset_gen()
        reset_gen()
        assert gen() == 'PHE1'


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TestTimeline:
    def test_starts_at_t0(self):
        tl = Timeline()
        assert tl.current() == 'T0'

    def test_advance_returns_t1(self):
        tl = Timeline()
        assert tl.advance() == 'T1'

    def test_advance_updates_current(self):
        tl = Timeline()
        tl.advance()
        assert tl.current() == 'T1'

    def test_multiple_advances(self):
        tl = Timeline()
        states = [tl.advance() for _ in range(5)]
        assert states == ['T1', 'T2', 'T3', 'T4', 'T5']
        assert tl.current() == 'T5'

    def test_all_states_initial(self):
        tl = Timeline()
        assert tl.all_states() == ['T0']

    def test_all_states_after_advances(self):
        tl = Timeline()
        tl.advance()
        tl.advance()
        assert tl.all_states() == ['T0', 'T1', 'T2']

    def test_all_states_returns_copy(self):
        tl = Timeline()
        states = tl.all_states()
        states.append('TAMPERED')
        assert tl.all_states() == ['T0']

    def test_independent_timelines(self):
        tl1 = Timeline()
        tl2 = Timeline()
        tl1.advance()
        tl1.advance()
        assert tl2.current() == 'T0'
        assert tl2.all_states() == ['T0']
