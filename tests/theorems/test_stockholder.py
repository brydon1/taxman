"""
Tests for main/theorems/stockholder.py — STOCKHOLDER abstract theorem.

The theorem is triggered by goal_abstract(db, 'STOCKHOLDER', owner, corp[, time])
and chains: ISSUE ?C ?S → STOCK ?S → PIECE-OF ?P ?S → OWN ?O ?P[?T].

Coverage:
  - Basic chain succeeds when all links present (time-free OWN)
  - Basic chain succeeds when OWN is time-indexed
  - Time token argument restricts OWN lookup to that time
  - Wrong time token yields nothing
  - Missing any link in the chain yields nothing
  - Multiple stockholders of same corp all returned
  - Multiple stock classes of same corp — stockholder via any class
  - Preferred vs common — no distinction at this theorem level
  - Direct DB entry bypasses theorem (goal_abstract semantics)
  - Query with variable owner enumerates all stockholders
  - Query with variable corp enumerates all corps
  - Non-stock issues (bonds) do not satisfy theorem (STOCK predicate absent)
"""
import pytest

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract
import main.theorems.stockholder  # registers the theorem as a side effect  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_minimal(db: Database, *, time: str | None = None) -> None:
    """Assert a minimal Phellis-style stockholder chain in *db*.

    Phellis owns 250 shares of NJ common stock (PHE2) via piece PHE5.
    """
    db.assert_('CORPORATION', 'NEW-JERSEY')
    db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
    db.assert_('STOCK', 'PHE2')
    db.assert_('COMMON', 'PHE2')
    db.assert_('PIECE-OF', 'PHE5', 'PHE2')
    db.assert_('NSHARES', 'PHE5', 250)
    if time is None:
        db.assert_('OWN', 'PHELLIS', 'PHE5')
    else:
        db.assert_('OWN', 'PHELLIS', 'PHE5', time)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return Database()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_theorem_registered(self):
        assert 'STOCKHOLDER' in ABSTRACT_THEOREMS

    def test_registered_value_is_callable(self):
        assert callable(ABSTRACT_THEOREMS['STOCKHOLDER'])


# ---------------------------------------------------------------------------
# Basic chain — time-free OWN
# ---------------------------------------------------------------------------

class TestBasicChainTimeFree:
    def test_ground_owner_and_corp_succeeds(self, db):
        _setup_minimal(db)
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert len(results) >= 1

    def test_wrong_owner_yields_nothing(self, db):
        _setup_minimal(db)
        results = list(goal_abstract(db, 'STOCKHOLDER', 'DELAWARE', 'NEW-JERSEY'))
        assert results == []

    def test_wrong_corp_yields_nothing(self, db):
        _setup_minimal(db)
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'DELAWARE'))
        assert results == []

    def test_result_binds_stock_and_piece(self, db):
        _setup_minimal(db)
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert any(r.get('S') == 'PHE2' and r.get('P') == 'PHE5' for r in results)


# ---------------------------------------------------------------------------
# Basic chain — time-indexed OWN
# ---------------------------------------------------------------------------

class TestBasicChainTimeIndexed:
    def test_time_indexed_own_succeeds_without_time_arg(self, db):
        _setup_minimal(db, time='T0')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert len(results) >= 1

    def test_time_indexed_own_binds_T_variable(self, db):
        _setup_minimal(db, time='T0')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert any(r.get('T') == 'T0' for r in results)

    def test_time_arg_matches_correct_time(self, db):
        _setup_minimal(db, time='T0')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY', 'T0'))
        assert len(results) >= 1

    def test_time_arg_wrong_time_yields_nothing(self, db):
        _setup_minimal(db, time='T0')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY', 'T9'))
        assert results == []

    def test_time_variable_arg_enumerates_times(self, db):
        _setup_minimal(db, time='T0')
        db.assert_('OWN', 'PHELLIS', 'PHE5', 'T1')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY', '?T'))
        times = {r['T'] for r in results}
        assert times == {'T0', 'T1'}


# ---------------------------------------------------------------------------
# Missing links in the chain
# ---------------------------------------------------------------------------

class TestMissingLinks:
    def test_missing_issue_yields_nothing(self, db):
        # No ISSUE assertion
        db.assert_('STOCK', 'PHE2')
        db.assert_('PIECE-OF', 'PHE5', 'PHE2')
        db.assert_('OWN', 'PHELLIS', 'PHE5')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert results == []

    def test_missing_stock_predicate_yields_nothing(self, db):
        # ISSUE exists but no STOCK — bonds e.g.
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE3')
        db.assert_('BOND', 'PHE3')       # not a STOCK
        db.assert_('PIECE-OF', 'PHE5', 'PHE3')
        db.assert_('OWN', 'PHELLIS', 'PHE5')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert results == []

    def test_missing_piece_of_yields_nothing(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        db.assert_('STOCK', 'PHE2')
        # No PIECE-OF
        db.assert_('OWN', 'PHELLIS', 'PHE2')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert results == []

    def test_missing_own_yields_nothing(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        db.assert_('STOCK', 'PHE2')
        db.assert_('PIECE-OF', 'PHE5', 'PHE2')
        # No OWN
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert results == []


# ---------------------------------------------------------------------------
# Variable owner / corp
# ---------------------------------------------------------------------------

class TestVariableQueries:
    def test_variable_owner_finds_all_stockholders(self, db):
        _setup_minimal(db, time='T0')
        # Add a second stockholder
        db.assert_('PIECE-OF', 'PHE6', 'PHE2')
        db.assert_('OWN', 'DELAWARE', 'PHE6', 'T0')
        results = list(goal_abstract(db, 'STOCKHOLDER', '?O', 'NEW-JERSEY', 'T0'))
        owners = {r['O'] for r in results}
        assert owners == {'PHELLIS', 'DELAWARE'}

    def test_variable_corp_finds_all_corps(self, db):
        # Phellis owns stock in both NJ and DE
        _setup_minimal(db)
        db.assert_('CORPORATION', 'DELAWARE')
        db.assert_('ISSUE', 'DELAWARE', 'PHE31')
        db.assert_('STOCK', 'PHE31')
        db.assert_('COMMON', 'PHE31')
        db.assert_('PIECE-OF', 'PHE28', 'PHE31')
        db.assert_('OWN', 'PHELLIS', 'PHE28')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', '?C'))
        corps = {r['C'] for r in results}
        assert corps == {'NEW-JERSEY', 'DELAWARE'}

    def test_all_variables_enumerates_all_pairs(self, db):
        _setup_minimal(db, time='T0')
        results = list(goal_abstract(db, 'STOCKHOLDER', '?O', '?C', 'T0'))
        assert any(r.get('O') == 'PHELLIS' and r.get('C') == 'NEW-JERSEY' for r in results)


# ---------------------------------------------------------------------------
# Multiple stock classes
# ---------------------------------------------------------------------------

class TestMultipleStockClasses:
    def test_stockholder_via_either_stock_class(self, db):
        # NJ has both preferred (PHE1) and common (PHE2)
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE1')
        db.assert_('STOCK', 'PHE1')
        db.assert_('PREFERRED', 'PHE1')
        db.assert_('PIECE-OF', 'PHE4', 'PHE1')
        db.assert_('OWN', 'HOLDER-A', 'PHE4')

        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        db.assert_('STOCK', 'PHE2')
        db.assert_('COMMON', 'PHE2')
        db.assert_('PIECE-OF', 'PHE5', 'PHE2')
        db.assert_('OWN', 'HOLDER-B', 'PHE5')

        results_a = list(goal_abstract(db, 'STOCKHOLDER', 'HOLDER-A', 'NEW-JERSEY'))
        results_b = list(goal_abstract(db, 'STOCKHOLDER', 'HOLDER-B', 'NEW-JERSEY'))
        assert len(results_a) >= 1
        assert len(results_b) >= 1

    def test_all_stockholders_across_classes(self, db):
        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE1')
        db.assert_('STOCK', 'PHE1')
        db.assert_('PIECE-OF', 'PHE4', 'PHE1')
        db.assert_('OWN', 'HOLDER-A', 'PHE4')

        db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
        db.assert_('STOCK', 'PHE2')
        db.assert_('PIECE-OF', 'PHE5', 'PHE2')
        db.assert_('OWN', 'HOLDER-B', 'PHE5')

        results = list(goal_abstract(db, 'STOCKHOLDER', '?O', 'NEW-JERSEY'))
        owners = {r['O'] for r in results}
        assert owners == {'HOLDER-A', 'HOLDER-B'}


# ---------------------------------------------------------------------------
# Direct DB entry bypasses theorem (goal_abstract semantics)
# ---------------------------------------------------------------------------

class TestDirectDBBypass:
    def test_direct_db_entry_returned_without_running_chain(self, db):
        # Assert STOCKHOLDER directly — no ISSUE/STOCK/PIECE-OF/OWN needed
        db.assert_('STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        assert results == [{}]

    def test_direct_db_entry_shadows_chain(self, db):
        # Even if chain facts exist, direct entry is returned (not theorem)
        db.assert_('STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY')
        _setup_minimal(db)
        results = list(goal_abstract(db, 'STOCKHOLDER', 'PHELLIS', 'NEW-JERSEY'))
        # Should be exactly [{}] from the direct entry, not the chain result
        assert results == [{}]


# ---------------------------------------------------------------------------
# Wrong arity
# ---------------------------------------------------------------------------

class TestWrongArity:
    def test_zero_args_yields_nothing(self, db):
        _setup_minimal(db)
        results = list(ABSTRACT_THEOREMS['STOCKHOLDER'](db))
        assert results == []

    def test_one_arg_yields_nothing(self, db):
        _setup_minimal(db)
        results = list(ABSTRACT_THEOREMS['STOCKHOLDER'](db, 'PHELLIS'))
        assert results == []

    def test_four_args_yields_nothing(self, db):
        _setup_minimal(db)
        results = list(ABSTRACT_THEOREMS['STOCKHOLDER'](db, 'A', 'B', 'C', 'D'))
        assert results == []
