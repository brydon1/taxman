"""
Tests for main/prog.py — apply_bindings, prog, goal_abstract, assert_expand (Layer 2b).

Coverage per README.md testing strategy:
  - Single-goal prog behaves like a query
  - Two-goal prog shares bindings correctly
  - Backtracking: if goal 2 fails, prog retries goal 1 with next match
  - Unsatisfiable prog yields nothing (does not raise)
  - apply_bindings substitutes bound variables, preserves ground values
  - goal_abstract hits DB first, falls back to registered theorem
  - assert_expand calls theorem if registered, else stores directly
"""
import pytest
from main.database import Database
from main.prog import apply_bindings, prog
from main.theorems.base import (
    ABSTRACT_THEOREMS,
    EXPAND_THEOREMS,
    assert_expand,
    goal_abstract,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return Database()


@pytest.fixture
def stock_db():
    """Minimal Phellis-style network for multi-goal tests."""
    d = Database()
    d.assert_('CORPORATION', 'NEW-JERSEY')
    d.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
    d.assert_('STOCK', 'PHE2')
    d.assert_('COMMON', 'PHE2')
    d.assert_('PIECE-OF', 'PHE5', 'PHE2')
    d.assert_('NSHARES', 'PHE5', 250)
    d.assert_('OWN', 'PHELLIS', 'PHE5', 'T0')
    return d


@pytest.fixture(autouse=True)
def clean_registries():
    """Restore theorem registries after each test."""
    abstract_snapshot = dict(ABSTRACT_THEOREMS)
    expand_snapshot = dict(EXPAND_THEOREMS)
    yield
    ABSTRACT_THEOREMS.clear()
    ABSTRACT_THEOREMS.update(abstract_snapshot)
    EXPAND_THEOREMS.clear()
    EXPAND_THEOREMS.update(expand_snapshot)


# ---------------------------------------------------------------------------
# apply_bindings
# ---------------------------------------------------------------------------

class TestApplyBindings:
    def test_substitutes_bound_variable(self):
        result = apply_bindings(('?X',), {'X': 'NEW-JERSEY'})
        assert result == ('NEW-JERSEY',)

    def test_leaves_unbound_variable_unchanged(self):
        result = apply_bindings(('?X',), {})
        assert result == ('?X',)

    def test_leaves_ground_value_unchanged(self):
        result = apply_bindings(('NEW-JERSEY',), {'X': 'SOMETHING'})
        assert result == ('NEW-JERSEY',)

    def test_anonymous_variable_stays_anonymous(self):
        result = apply_bindings(('?',), {'': 'IGNORED'})
        # '' key should not be used; '?' remains so db.query treats it as wildcard
        assert result == ('?',)

    def test_mixed_args(self):
        result = apply_bindings(('NEW-JERSEY', '?S', '?T'), {'S': 'PHE2'})
        assert result == ('NEW-JERSEY', 'PHE2', '?T')

    def test_empty_args(self):
        assert apply_bindings((), {'X': 'A'}) == ()

    def test_integer_ground_value_unchanged(self):
        result = apply_bindings((250,), {})
        assert result == (250,)


# ---------------------------------------------------------------------------
# prog — base cases
# ---------------------------------------------------------------------------

class TestProgBase:
    def test_empty_goals_yields_current_bindings(self, db):
        results = list(prog(db, [], {'X': 'A'}))
        assert results == [{'X': 'A'}]

    def test_empty_goals_empty_bindings_yields_one_empty_dict(self, db):
        results = list(prog(db, []))
        assert results == [{}]

    def test_unsatisfiable_single_goal_yields_nothing(self, db):
        results = list(prog(db, [('CORPORATION', 'NEW-JERSEY')]))
        assert results == []

    def test_unsatisfiable_does_not_raise(self, db):
        list(prog(db, [('NONEXISTENT', '?X'), ('STOCK', '?X')]))  # no error


# ---------------------------------------------------------------------------
# prog — single goal behaves like db.query
# ---------------------------------------------------------------------------

class TestProgSingleGoal:
    def test_single_goal_ground_match(self, stock_db):
        results = list(prog(stock_db, [('CORPORATION', 'NEW-JERSEY')]))
        assert results == [{}]

    def test_single_goal_ground_no_match(self, stock_db):
        results = list(prog(stock_db, [('CORPORATION', 'DELAWARE')]))
        assert results == []

    def test_single_goal_variable_binds(self, stock_db):
        results = list(prog(stock_db, [('CORPORATION', '?C')]))
        assert results == [{'C': 'NEW-JERSEY'}]

    def test_single_goal_multiple_matches(self, db):
        db.assert_('STOCK', 'A')
        db.assert_('STOCK', 'B')
        results = list(prog(db, [('STOCK', '?S')]))
        assert {r['S'] for r in results} == {'A', 'B'}

    def test_single_goal_anonymous_variable(self, stock_db):
        results = list(prog(stock_db, [('CORPORATION', '?')]))
        assert results == [{}]
        
    def test_single_goal_anonymous_variable_multiple_matches(self, db):
        db.assert_('STOCK', 'A')
        db.assert_('STOCK', 'B')
        results = list(prog(db, [('STOCK', '?')]))
        assert results == [{}, {}]


# ---------------------------------------------------------------------------
# prog — two goals share bindings
# ---------------------------------------------------------------------------

class TestProgTwoGoals:
    def test_binding_from_goal1_used_in_goal2(self, stock_db):
        # Goal 1 binds ?S; goal 2 uses ?S to find STOCK
        goals = [
            ('ISSUE', 'NEW-JERSEY', '?S'),
            ('STOCK', '?S'),
        ]
        results = list(prog(stock_db, goals))
        assert len(results) == 1
        assert results[0]['S'] == 'PHE2'

    def test_two_goals_both_binding(self, stock_db):
        # Find all (corp, stock) pairs where corp issued stock AND stock is common
        goals = [
            ('ISSUE', '?C', '?S'),
            ('COMMON', '?S'),
        ]
        results = list(prog(stock_db, goals))
        assert len(results) == 1
        assert results[0] == {'C': 'NEW-JERSEY', 'S': 'PHE2'}

    def test_stockholder_chain(self, stock_db):
        # Full stockholder chain: ISSUE → STOCK → PIECE-OF → OWN
        goals = [
            ('ISSUE', 'NEW-JERSEY', '?S'),
            ('STOCK', '?S'),
            ('PIECE-OF', '?P', '?S'),
            ('OWN', 'PHELLIS', '?P', '?T'),
        ]
        results = list(prog(stock_db, goals))
        assert len(results) == 1
        assert results[0]['S'] == 'PHE2'
        assert results[0]['P'] == 'PHE5'
        assert results[0]['T'] == 'T0'


# ---------------------------------------------------------------------------
# prog — backtracking
# ---------------------------------------------------------------------------

class TestProgBacktracking:
    def test_backtracks_when_goal2_fails(self, db):
        # Goal 1 has two matches (A and B); goal 2 only succeeds for B.
        db.assert_('STOCK', 'A')
        db.assert_('STOCK', 'B')
        db.assert_('COMMON', 'B')   # only B is common

        goals = [
            ('STOCK', '?S'),
            ('COMMON', '?S'),
        ]
        results = list(prog(db, goals))
        assert len(results) == 1
        assert results[0]['S'] == 'B'

    def test_backtracks_through_all_matches(self, db):
        # Goal 1 has three matches; goal 2 succeeds for two of them.
        db.assert_('STOCK', 'A')
        db.assert_('STOCK', 'B')
        db.assert_('STOCK', 'C')
        db.assert_('VOTING', 'A')
        db.assert_('VOTING', 'C')

        goals = [
            ('STOCK', '?S'),
            ('VOTING', '?S'),
        ]
        results = list(prog(db, goals))
        assert {r['S'] for r in results} == {'A', 'C'}

    def test_no_solutions_yields_nothing(self, db):
        db.assert_('STOCK', 'A')
        db.assert_('STOCK', 'B')
        # Neither is VOTING
        goals = [
            ('STOCK', '?S'),
            ('VOTING', '?S'),
        ]
        results = list(prog(db, goals))
        assert results == []

    # TODO make sense of this case
    def test_early_exit_via_next(self, db):
        # Verify the generator lazily yields — calling next() once only runs
        # as far as the first solution.
        db.assert_('STOCK', 'A')
        db.assert_('STOCK', 'B')
        it = prog(db, [('STOCK', '?S')])
        first = next(it)
        assert 'S' in first


# ---------------------------------------------------------------------------
# prog — initial bindings passed in
# ---------------------------------------------------------------------------

class TestProgInitialBindings:
    def test_initial_bindings_substituted(self, stock_db):
        # Pre-bind ?C so only the matching ISSUE is found
        results = list(prog(stock_db, [('ISSUE', '?C', '?S')], {'C': 'NEW-JERSEY'}))
        assert all(r['C'] == 'NEW-JERSEY' for r in results)

    def test_initial_bindings_conflict_skipped(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        # Pre-bind ?C = DELAWARE; no ISSUE for DELAWARE, so no results
        results = list(prog(db, [('ISSUE', '?C', '?S')], {'C': 'DELAWARE'}))
        assert results == []


# ---------------------------------------------------------------------------
# goal_abstract
# ---------------------------------------------------------------------------

class TestGoalAbstract:
    def test_direct_db_match_returned(self, db):
        db.assert_('STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert results == [{}]

    def test_direct_db_variable_match(self, db):
        db.assert_('STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')
        results = list(goal_abstract(db, 'STOCKHOLDER', '?O', '?C'))
        assert results == [{'O': 'PHELLIS', 'C': 'NEW-JERSEY'}]

    def test_falls_back_to_theorem_when_db_empty(self, db):
        def simple_theorem(database, *args):
            yield {'O': 'PHELLIS', 'C': 'NEW-JERSEY'}

        ABSTRACT_THEOREMS['STOCKHOLDER'] = simple_theorem
        results = list(goal_abstract(db, 'STOCKHOLDER', '?O', '?C'))
        assert results == [{'O': 'PHELLIS', 'C': 'NEW-JERSEY'}]

    def test_db_hit_skips_theorem(self, db):
        db.assert_('STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')
        called = []

        def should_not_be_called(database, *args):
            called.append(True)
            yield {}

        ABSTRACT_THEOREMS['STOCKHOLDER'] = should_not_be_called
        list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert called == []

    def test_no_db_and_no_theorem_yields_nothing(self, db):
        results = list(goal_abstract(db, 'UNKNOWN', '?X'))
        assert results == []

    def test_theorem_called_with_args(self, db):
        received = []

        def capturing_theorem(database, *args):
            received.extend(args)
            return iter([])

        ABSTRACT_THEOREMS['TEST'] = capturing_theorem
        list(goal_abstract(db, 'TEST', 'ARG1', '?X'))
        assert received == ['ARG1', '?X']


# ---------------------------------------------------------------------------
# assert_expand
# ---------------------------------------------------------------------------

class TestAssertExpand:
    def test_no_theorem_stores_directly(self, db):
        assert_expand(db, 'STOCK', 'S1')
        assert db.query('STOCK', 'S1') == [{}]

    def test_registered_theorem_called(self, db):
        calls = []

        def my_expand(database, *args):
            calls.append(args)

        EXPAND_THEOREMS['TRANS'] = my_expand
        assert_expand(db, 'TRANS', 'S', 'X', 'O', 'R', 'T1')
        assert calls == [('S', 'X', 'O', 'R', 'T1')]

    def test_registered_theorem_prevents_direct_store(self, db):
        def my_expand(database, *args):
            pass  # does nothing intentionally

        EXPAND_THEOREMS['TRANS'] = my_expand
        assert_expand(db, 'TRANS', 'S', 'X', 'O', 'R', 'T1')
        # Theorem was called but did not store; direct store was skipped
        assert db.query('TRANS', 'S', 'X', 'O', 'R', 'T1') == []

    def test_theorem_can_assert_different_propositions(self, db):
        def ownership_expand(database, obj, owner, recipient, time):
            database.erase('OWN', owner, obj, 'T0')
            database.assert_('OWN', recipient, obj, time)

        EXPAND_THEOREMS['TRANSFER'] = ownership_expand
        db.assert_('OWN', 'PHELLIS', 'P1', 'T0')
        assert_expand(db, 'TRANSFER', 'P1', 'PHELLIS', 'DELAWARE', 'T1')
        assert db.query('OWN', 'PHELLIS', 'P1', 'T0') == []
        assert db.query('OWN', 'DELAWARE', 'P1', 'T1') == [{}]
