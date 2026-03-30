"""
Tests for main/theorems/control.py — CONTROL abstract theorem.

CONTROL(X, Y, T) requires X owns ≥ 80 % of every voting stock class issued
by Y AND ≥ 80 % of every non-voting stock class issued by Y, at time T.

Coverage:
  - Registration
  - 100 % ownership → control
  - Exactly 80 % → control (boundary)
  - 79 % → no control (just below boundary)
  - No voting stock issued → no control
  - Non-voting stock only → no control (no voting class)
  - Multiple voting classes: must pass each independently
  - Multiple non-voting classes: aggregate across all non-voting classes
  - Mixed voting + non-voting: both thresholds required
  - Fails non-voting threshold even when voting threshold passes
  - Wrong time → no control
  - Variable owner / corp / time patterns
  - Deduplication: multiple STOCKHOLDER solutions for same triple count once
  - Direct DB entry bypasses theorem
  - Wrong arity → yields nothing
  - Bond issued by corp does not count as stock class
  - Zero shares outstanding in a class → skipped (degenerate)
"""
import pytest

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract
import main.theorems.stockholder  # noqa: F401 — registers STOCKHOLDER first
import main.theorems.control      # noqa: F401 — registers CONTROL


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _add_stock_class(
    db: Database,
    corp: str,
    stock_sym: str,
    *,
    voting: bool = True,
    preferred: bool = False,
) -> None:
    """Assert ISSUE, STOCK, and optionally VOTING/PREFERRED for a stock class."""
    db.assert_('ISSUE', corp, stock_sym)
    db.assert_('STOCK', stock_sym)
    if voting:
        db.assert_('VOTING', stock_sym)
    if preferred:
        db.assert_('PREFERRED', stock_sym)
    else:
        db.assert_('COMMON', stock_sym)


def _add_piece(
    db: Database,
    piece: str,
    stock_sym: str,
    n: int,
    owner: str,
    time: str,
) -> None:
    """Assert PIECE-OF, NSHARES, and OWN(owner, piece, time)."""
    db.assert_('PIECE-OF', piece, stock_sym)
    db.assert_('NSHARES', piece, n)
    db.assert_('OWN', owner, piece, time)


@pytest.fixture
def db():
    return Database()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_theorem_registered(self):
        assert 'CONTROL' in ABSTRACT_THEOREMS

    def test_callable(self):
        assert callable(ABSTRACT_THEOREMS['CONTROL'])


# ---------------------------------------------------------------------------
# 100 % single voting class
# ---------------------------------------------------------------------------

class TestFullOwnership:
    def test_100_percent_single_voting_class(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1

    def test_yields_empty_binding_for_ground_args(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == [{}]


# ---------------------------------------------------------------------------
# 80 % boundary
# ---------------------------------------------------------------------------

class TestEightyPercentBoundary:
    def _setup(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 80, 'OWNER-X', 'T0')
        _add_piece(db, 'P2', 'S1', 20, 'OWNER-Y', 'T0')

    def test_exactly_80_percent_is_control(self, db):
        self._setup(db)
        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1

    def test_79_percent_is_not_control(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 79, 'OWNER-X', 'T0')
        _add_piece(db, 'P2', 'S1', 21, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []

    def test_81_percent_is_control(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 81, 'OWNER-X', 'T0')
        _add_piece(db, 'P2', 'S1', 19, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# No voting stock → no control
# ---------------------------------------------------------------------------

class TestNoVotingStock:
    def test_no_stock_at_all_yields_nothing(self, db):
        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []

    def test_no_voting_stock_yields_nothing(self, db):
        # Corp has only non-voting stock
        _add_stock_class(db, 'CORP-A', 'S1', voting=False)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []

    def test_bond_issued_does_not_create_stock_class(self, db):
        # Issue a bond (no STOCK assertion) — should not count toward control
        db.assert_('ISSUE', 'CORP-A', 'BOND1')
        db.assert_('BOND', 'BOND1')
        db.assert_('PIECE-OF', 'P1', 'BOND1')
        db.assert_('NSHARES', 'P1', 100)
        db.assert_('OWN', 'OWNER-X', 'P1', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []


# ---------------------------------------------------------------------------
# Multiple voting classes
# ---------------------------------------------------------------------------

class TestMultipleVotingClasses:
    def test_must_pass_each_voting_class(self, db):
        # Two voting classes; owner controls S1 (100%) but not S2 (50%)
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        _add_stock_class(db, 'CORP-A', 'S2', voting=True)
        _add_piece(db, 'P2', 'S2', 50, 'OWNER-X', 'T0')
        _add_piece(db, 'P3', 'S2', 50, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []

    def test_passes_all_voting_classes(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 80, 'OWNER-X', 'T0')
        _add_piece(db, 'P2', 'S1', 20, 'OWNER-Y', 'T0')

        _add_stock_class(db, 'CORP-A', 'S2', voting=True)
        _add_piece(db, 'P3', 'S2', 90, 'OWNER-X', 'T0')
        _add_piece(db, 'P4', 'S2', 10, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Mixed voting and non-voting classes
# ---------------------------------------------------------------------------

class TestMixedClasses:
    def _setup_voting(self, db, owner_pct=100):
        _add_stock_class(db, 'CORP-A', 'S-VOTE', voting=True)
        _add_piece(db, 'PV1', 'S-VOTE', owner_pct, 'OWNER-X', 'T0')
        if owner_pct < 100:
            _add_piece(db, 'PV2', 'S-VOTE', 100 - owner_pct, 'OWNER-Y', 'T0')

    def test_passes_voting_fails_nonvoting(self, db):
        self._setup_voting(db, owner_pct=100)
        _add_stock_class(db, 'CORP-A', 'S-NVOTE', voting=False)
        _add_piece(db, 'PN1', 'S-NVOTE', 79, 'OWNER-X', 'T0')
        _add_piece(db, 'PN2', 'S-NVOTE', 21, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []

    def test_passes_both_thresholds(self, db):
        # _setup_voting(owner_pct=80) adds PV1(80,X) and PV2(20,Y) → X has 80%
        self._setup_voting(db, owner_pct=80)

        _add_stock_class(db, 'CORP-A', 'S-NVOTE', voting=False)
        _add_piece(db, 'PN1', 'S-NVOTE', 80, 'OWNER-X', 'T0')
        _add_piece(db, 'PN2', 'S-NVOTE', 20, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1

    def test_no_nonvoting_classes_satisfies_vacuously(self, db):
        # Only voting stock — non-voting requirement is vacuously met
        _add_stock_class(db, 'CORP-A', 'S-VOTE', voting=True)
        _add_piece(db, 'PV1', 'S-VOTE', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1

    def test_nonvoting_threshold_checked_in_aggregate(self, db):
        # S-NV1: X has 85/100; S-NV2: X has 75/100.
        # Per-class: S-NV2 fails (75 % < 80 %).
        # Aggregate: (85 + 75) / (100 + 100) = 80 % → control established.
        self._setup_voting(db, owner_pct=100)
        _add_stock_class(db, 'CORP-A', 'S-NV1', voting=False)
        _add_piece(db, 'PN1', 'S-NV1', 85, 'OWNER-X', 'T0')
        _add_piece(db, 'PN2', 'S-NV1', 15, 'OWNER-Y', 'T0')

        _add_stock_class(db, 'CORP-A', 'S-NV2', voting=False)
        _add_piece(db, 'PN3', 'S-NV2', 75, 'OWNER-X', 'T0')
        _add_piece(db, 'PN4', 'S-NV2', 25, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1

    def test_nonvoting_aggregate_below_threshold(self, db):
        # S-NV1: X has 85/100; S-NV2: X has 70/100.
        # Aggregate: (85 + 70) / (100 + 100) = 77.5 % < 80 % → no control.
        self._setup_voting(db, owner_pct=100)
        _add_stock_class(db, 'CORP-A', 'S-NV1', voting=False)
        _add_piece(db, 'PN1', 'S-NV1', 85, 'OWNER-X', 'T0')
        _add_piece(db, 'PN2', 'S-NV1', 15, 'OWNER-Y', 'T0')

        _add_stock_class(db, 'CORP-A', 'S-NV2', voting=False)
        _add_piece(db, 'PN3', 'S-NV2', 70, 'OWNER-X', 'T0')
        _add_piece(db, 'PN4', 'S-NV2', 30, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == []


# ---------------------------------------------------------------------------
# Time sensitivity
# ---------------------------------------------------------------------------

class TestTimeSensitivity:
    def test_control_at_correct_time(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T1')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T1'))
        assert len(results) == 1

    def test_wrong_time_yields_nothing(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        # Query at T1 — ownership was at T0
        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T1'))
        assert results == []

    def test_control_lost_after_transfer(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        db.assert_('PIECE-OF', 'P1', 'S1')
        db.assert_('NSHARES', 'P1', 100)
        # At T0 OWNER-X controls; at T1 ownership transferred to OWNER-Y
        db.assert_('OWN', 'OWNER-X', 'P1', 'T0')
        db.assert_('OWN', 'OWNER-Y', 'P1', 'T1')

        assert list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0')) != []
        assert list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T1')) == []


# ---------------------------------------------------------------------------
# Variable pattern queries
# ---------------------------------------------------------------------------

class TestVariablePatterns:
    def test_variable_owner(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', '?X', 'CORP-A', 'T0'))
        assert len(results) == 1
        assert results[0]['X'] == 'OWNER-X'

    def test_variable_corp(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', '?C', 'T0'))
        assert len(results) == 1
        assert results[0]['C'] == 'CORP-A'

    def test_variable_time(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T2')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', '?T'))
        assert len(results) == 1
        assert results[0]['T'] == 'T2'

    def test_all_variables(self, db):
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', '?X', '?Y', '?T'))
        assert len(results) == 1
        r = results[0]
        assert r['X'] == 'OWNER-X'
        assert r['Y'] == 'CORP-A'
        assert r['T'] == 'T0'

    def test_variable_owner_finds_multiple_controllers(self, db):
        # Two owners each fully control separate corps
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        _add_stock_class(db, 'CORP-B', 'S2', voting=True)
        _add_piece(db, 'P2', 'S2', 100, 'OWNER-Y', 'T0')

        results = list(goal_abstract(db, 'CONTROL', '?X', '?Y', 'T0'))
        pairs = {(r['X'], r['Y']) for r in results}
        assert ('OWNER-X', 'CORP-A') in pairs
        assert ('OWNER-Y', 'CORP-B') in pairs


# ---------------------------------------------------------------------------
# Deduplication: multiple STOCKHOLDER solutions → single control check
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_multiple_stock_classes_yield_one_control_result(self, db):
        # OWNER-X holds stock in two voting classes of CORP-A
        # STOCKHOLDER would yield two bindings (one per class) but CONTROL should
        # deduplicate and yield a single result.
        _add_stock_class(db, 'CORP-A', 'S1', voting=True)
        _add_piece(db, 'P1', 'S1', 100, 'OWNER-X', 'T0')

        _add_stock_class(db, 'CORP-A', 'S2', voting=True)
        _add_piece(db, 'P2', 'S2', 100, 'OWNER-X', 'T0')

        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Direct DB entry bypasses theorem
# ---------------------------------------------------------------------------

class TestDirectDBBypass:
    def test_direct_entry_returned_without_running_chain(self, db):
        db.assert_('CONTROL', 'OWNER-X', 'CORP-A', 'T0')
        results = list(goal_abstract(db, 'CONTROL', 'OWNER-X', 'CORP-A', 'T0'))
        assert results == [{}]

    def test_direct_entry_with_variable(self, db):
        db.assert_('CONTROL', 'OWNER-X', 'CORP-A', 'T0')
        results = list(goal_abstract(db, 'CONTROL', '?X', 'CORP-A', 'T0'))
        assert results == [{'X': 'OWNER-X'}]


# ---------------------------------------------------------------------------
# Wrong arity
# ---------------------------------------------------------------------------

class TestWrongArity:
    def test_zero_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['CONTROL'](db)) == []

    def test_one_arg_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['CONTROL'](db, 'OWNER-X')) == []

    def test_two_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['CONTROL'](db, 'OWNER-X', 'CORP-A')) == []

    def test_four_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['CONTROL'](db, 'A', 'B', 'C', 'D')) == []


# ---------------------------------------------------------------------------
# Phellis-style scenario: NJ controls Delaware after reorganization
# ---------------------------------------------------------------------------

class TestPhellisStyle:
    def test_nj_controls_delaware(self, db):
        """After the reorganization NJ held 100% of Delaware common (voting).

        This mirrors phellis_expected.py: nj_controls_delaware_at_t2 = true.
        Delaware common (PHE31) is voting stock issued by Delaware.
        NJ holds piece PHE-NJ-PIECE (100 shares out of 100 total) at T2.
        """
        db.assert_('ISSUE', 'DELAWARE', 'PHE31')
        db.assert_('STOCK', 'PHE31')
        db.assert_('COMMON', 'PHE31')
        db.assert_('VOTING', 'PHE31')
        db.assert_('PIECE-OF', 'PHE-NJ-PIECE', 'PHE31')
        db.assert_('NSHARES', 'PHE-NJ-PIECE', 100)
        db.assert_('OWN', 'NEW-JERSEY', 'PHE-NJ-PIECE', 'T2')

        results = list(goal_abstract(db, 'CONTROL', 'NEW-JERSEY', 'DELAWARE', 'T2'))
        assert len(results) == 1

    def test_nj_does_not_control_delaware_after_distribution(self, db):
        """After NJ distributes Delaware common to its shareholders, NJ loses control."""
        db.assert_('ISSUE', 'DELAWARE', 'PHE31')
        db.assert_('STOCK', 'PHE31')
        db.assert_('COMMON', 'PHE31')
        db.assert_('VOTING', 'PHE31')
        db.assert_('PIECE-OF', 'PHE-PHELLIS-PIECE', 'PHE31')
        db.assert_('NSHARES', 'PHE-PHELLIS-PIECE', 100)
        # After distribution at T3, PHELLIS (not NJ) owns the Delaware shares
        db.assert_('OWN', 'PHELLIS', 'PHE-PHELLIS-PIECE', 'T3')

        results = list(goal_abstract(db, 'CONTROL', 'NEW-JERSEY', 'DELAWARE', 'T3'))
        assert results == []
