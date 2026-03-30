"""
Tests for main/database.py — Database layer (Layer 1).

Coverage per README.md testing strategy:
  - Assert and retrieve a proposition
  - Erase removes exactly the right tuple
  - Query with all variables ground (verify mode)
  - Query with one unbound variable (search mode)
  - Query with multiple unbound variables (enumerate mode)
  - No match returns empty list, not an error
  - Additional: idempotent assert, anonymous variable, repeated variable,
    arity mismatch, time-indexed propositions
"""
import pytest
from main.database import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return Database()


@pytest.fixture
def phellis_db():
    """Minimal Phellis initial-state network (CLAUDE.md §8)."""
    d = Database()
    d.assert_('CORPORATION', 'NEW-JERSEY')
    d.assert_('CORPORATION', 'DELAWARE')
    d.assert_('ISSUE', 'NEW-JERSEY', 'PHE1')
    d.assert_('STOCK', 'PHE1')
    d.assert_('PREFERRED', 'PHE1')
    d.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
    d.assert_('STOCK', 'PHE2')
    d.assert_('COMMON', 'PHE2')
    d.assert_('PIECE-OF', 'PHE5', 'PHE2')
    d.assert_('NSHARES', 'PHE5', 250)
    d.assert_('OWN', 'PHELLIS', 'PHE5', 'T0')
    return d


# ---------------------------------------------------------------------------
# assert_ — basic storage
# ---------------------------------------------------------------------------

class TestAssert:
    def test_assert_stores_proposition(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        assert db.query('CORPORATION', 'NEW-JERSEY') == [{}]

    def test_assert_is_idempotent(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'NEW-JERSEY')
        assert len(db.all_entries('CORPORATION')) == 1

    def test_assert_multiple_propositions_same_predicate(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')
        assert len(db.all_entries('CORPORATION')) == 2

    def test_assert_multi_arg_proposition(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1', 'T4')
        assert db.query('OWN', 'PHELLIS', 'P1', 'T4') == [{}]

    def test_assert_different_arities_stored_separately(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1')
        db.assert_('OWN', 'PHELLIS', 'P1', 'T4')
        assert len(db.all_entries('OWN')) == 2


# ---------------------------------------------------------------------------
# erase — removal
# ---------------------------------------------------------------------------

class TestErase:
    def test_erase_removes_matching_proposition(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.erase('CORPORATION', 'NEW-JERSEY')
        assert db.query('CORPORATION', 'NEW-JERSEY') == []

    def test_erase_noop_on_absent_proposition(self, db):
        db.erase('CORPORATION', 'NEW-JERSEY')   # should not raise

    def test_erase_removes_only_exact_match(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')
        db.erase('CORPORATION', 'NEW-JERSEY')
        assert db.query('CORPORATION', 'NEW-JERSEY') == []
        assert db.query('CORPORATION', 'DELAWARE') == [{}]

    def test_erase_arity_specific(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1')
        db.assert_('OWN', 'PHELLIS', 'P1', 'T4')
        db.erase('OWN', 'PHELLIS', 'P1')
        assert db.query('OWN', 'PHELLIS', 'P1') == []
        assert db.query('OWN', 'PHELLIS', 'P1', 'T4') == [{}]

    def test_erase_then_reassert(self, db):
        db.assert_('STOCK', 'S1')
        db.erase('STOCK', 'S1')
        db.assert_('STOCK', 'S1')
        assert db.query('STOCK', 'S1') == [{}]


# ---------------------------------------------------------------------------
# query — ground verification
# ---------------------------------------------------------------------------

class TestQueryGround:
    def test_ground_match_returns_empty_dict(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        result = db.query('CORPORATION', 'NEW-JERSEY')
        assert result == [{}]

    def test_ground_no_match_returns_empty_list(self, db):
        result = db.query('CORPORATION', 'NEW-JERSEY')
        assert result == []

    def test_ground_wrong_predicate(self, db):
        db.assert_('STOCK', 'S1')
        assert db.query('CORPORATION', 'S1') == []

    def test_ground_multi_arg_match(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        assert db.query('ISSUE', 'NEW-JERSEY', 'PHE2') == [{}]

    def test_ground_multi_arg_partial_mismatch(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        assert db.query('ISSUE', 'DELAWARE', 'PHE2') == []

    def test_ground_integer_argument(self, db):
        db.assert_('NSHARES', 'PHE5', 250)
        assert db.query('NSHARES', 'PHE5', 250) == [{}]
        assert db.query('NSHARES', 'PHE5', 100) == []


# ---------------------------------------------------------------------------
# query — variable binding (single variable)
# ---------------------------------------------------------------------------

class TestQuerySingleVariable:
    def test_single_variable_binds_on_match(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        result = db.query('CORPORATION', '?X')
        assert result == [{'X': 'NEW-JERSEY'}]

    def test_single_variable_no_match(self, db):
        assert db.query('CORPORATION', '?X') == []

    def test_single_variable_multiple_matches(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')
        result = db.query('CORPORATION', '?X')
        assert len(result) == 2
        values = {r['X'] for r in result}
        assert values == {'NEW-JERSEY', 'DELAWARE'}

    def test_variable_in_first_arg(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        result = db.query('ISSUE', '?C', 'PHE2')
        assert result == [{'C': 'NEW-JERSEY'}]

    def test_variable_in_second_arg(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        result = db.query('ISSUE', 'NEW-JERSEY', '?S')
        assert result == [{'S': 'PHE2'}]


# ---------------------------------------------------------------------------
# query — multiple variables
# ---------------------------------------------------------------------------

class TestQueryMultipleVariables:
    def test_all_variables_enumerate(self, phellis_db):
        result = phellis_db.query('ISSUE', '?C', '?S')
        assert len(result) == 2
        corps = {r['C'] for r in result}
        stocks = {r['S'] for r in result}
        assert corps == {'NEW-JERSEY'}
        assert stocks == {'PHE1', 'PHE2'}

    def test_mixed_ground_and_variable(self, phellis_db):
        result = phellis_db.query('ISSUE', 'NEW-JERSEY', '?S')
        assert len(result) == 2
        assert {r['S'] for r in result} == {'PHE1', 'PHE2'}

    def test_three_arg_query(self, phellis_db):
        result = phellis_db.query('OWN', '?O', '?P', '?T')
        assert result == [{'O': 'PHELLIS', 'P': 'PHE5', 'T': 'T0'}]


# ---------------------------------------------------------------------------
# query — repeated variable (same variable must unify to same value)
# ---------------------------------------------------------------------------

class TestQueryRepeatedVariable:
    def test_repeated_variable_matches_when_consistent(self, db):
        db.assert_('SAME', 'A', 'A')
        result = db.query('SAME', '?X', '?X')
        assert result == [{'X': 'A'}]

    def test_repeated_variable_fails_when_inconsistent(self, db):
        db.assert_('SAME', 'A', 'B')
        result = db.query('SAME', '?X', '?X')
        assert result == []

    def test_repeated_variable_across_multiple_entries(self, db):
        db.assert_('SAME', 'A', 'A')
        db.assert_('SAME', 'B', 'B')
        db.assert_('SAME', 'A', 'B')
        result = db.query('SAME', '?X', '?X')
        assert len(result) == 2
        assert {r['X'] for r in result} == {'A', 'B'}


# ---------------------------------------------------------------------------
# query — anonymous variable '?'
# ---------------------------------------------------------------------------

class TestQueryAnonymousVariable:
    def test_anonymous_matches_any_value(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')
        result = db.query('CORPORATION', '?')
        assert len(result) == 2
        # Anonymous variable produces no binding key
        assert all(r == {} for r in result)

    def test_anonymous_mixed_with_named(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE1')
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        result = db.query('ISSUE', '?', '?S')
        assert len(result) == 2
        assert {r['S'] for r in result} == {'PHE1', 'PHE2'}
        # No key '' or key from anonymous
        assert all(len(r) == 1 for r in result)


# ---------------------------------------------------------------------------
# query — arity mismatch
# ---------------------------------------------------------------------------

class TestQueryArityMismatch:
    def test_arity_mismatch_returns_no_results(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1')
        db.assert_('OWN', 'TERRY', 'P2', 'T4')
        # Only 2-arg query should match 2-arg entry
        result = db.query('OWN', '?O', '?X')
        assert result == [{'O': 'PHELLIS', 'X': 'P1'}]

    def test_no_entries_empty_list(self, db):
        assert db.query('OWN', '?O', '?X') == []


# ---------------------------------------------------------------------------
# query — time-indexed propositions
# ---------------------------------------------------------------------------

class TestQueryTimeIndexed:
    def test_time_indexed_stored_and_retrieved(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1', 'T0')
        assert db.query('OWN', 'PHELLIS', 'P1', 'T0') == [{}]

    def test_time_indexed_variable_binds_time(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1', 'T0')
        result = db.query('OWN', 'PHELLIS', 'P1', '?T')
        assert result == [{'T': 'T0'}]

    def test_different_time_tokens_separate_entries(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1', 'T0')
        db.assert_('OWN', 'DELAWARE', 'P1', 'T1')
        result = db.query('OWN', '?O', 'P1', '?T')
        assert len(result) == 2
        owners = {r['O'] for r in result}
        assert owners == {'PHELLIS', 'DELAWARE'}

    def test_erase_time_indexed_proposition(self, db):
        db.assert_('OWN', 'PHELLIS', 'P1', 'T0')
        db.erase('OWN', 'PHELLIS', 'P1', 'T0')
        assert db.query('OWN', 'PHELLIS', 'P1', 'T0') == []


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_all_predicates_empty(self, db):
        assert db.all_predicates() == []

    def test_all_predicates_after_asserts(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('STOCK', 'S1')
        preds = set(db.all_predicates())
        assert preds == {'CORPORATION', 'STOCK'}

    def test_all_predicates_excludes_erased(self, db):
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.erase('CORPORATION', 'NEW-JERSEY')
        assert 'CORPORATION' not in db.all_predicates()

    def test_all_entries_returns_raw_tuples(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE1')
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        entries = db.all_entries('ISSUE')
        assert set(entries) == {('NEW-JERSEY', 'PHE1'), ('NEW-JERSEY', 'PHE2')}

    def test_all_entries_unknown_predicate(self, db):
        assert db.all_entries('NONEXISTENT') == []
