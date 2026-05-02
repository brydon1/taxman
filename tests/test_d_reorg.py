"""
Tests for main/theorems/d_reorg.py — D-REORGANIZATION abstract theorem.

D-Reorganization (§368(a)(1)(D)):
  Transfer of assets by one corporation (A) to another corporation (C),
  such that immediately after the transfer, A (or A's shareholders) controls C.

Key structural constraints (partial implementation per CLAUDE.md §9):
  - A must be a CORPORATION
  - A must transfer a property (PIECE-OF a non-STOCK class) to C
  - A must control C immediately after the transfer (CONTROL theorem, ≥80%)
  - Distribution requirement (§354/355) is NOT checked — partial only

Phellis case query (CLAUDE.md §5.5, Query 4):
  - D-Reorg(NJ, DELAWARE) → succeeds: NJ transfers assets, NJ controls DE after

Coverage:
  - Registration
  - Simple successful D-Reorg
  - Ground args yield empty binding
  - Multiple property transfers from A to C deduplicated to one result
  - Fails when A is not a CORPORATION
  - Fails when transferred object is stock (not property)
  - Fails when no TRANS from A to C exists
  - Fails when A does not control C after the transfer
  - Variable transferor / transferee / time patterns
  - All three variables
  - Direct DB entry bypasses theorem
  - Wrong arity yields nothing
  - Phellis-style: NJ transfers assets to DE, NJ controls DE → succeeds
  - Phellis-style: DE as transferor fails — no property transfer from DE to NJ
"""
import pytest

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract, assert_expand
import main.theorems.stockholder  # noqa: F401 — registers STOCKHOLDER
import main.theorems.control      # noqa: F401 — registers CONTROL (needs STOCKHOLDER)
import main.theorems.trans        # noqa: F401 — registers TRANS, SPLITPIECE
import main.theorems.d_reorg      # noqa: F401 — registers D-REORGANIZATION


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _setup_basic_d_reorg(db: Database) -> None:
    """
    Minimal successful D-Reorg:
      TRANSFEROR (CORPORATION) transfers property (PROP-P) to TRANSFEREE.
      TRANSFEROR holds 100% of TRANSFEREE's voting stock at T1 → controls TRANSFEREE.

    Stock ownership at T1 is asserted directly (no TRANS needed for that leg).
    """
    db.assert_('CORPORATION', 'TRANSFEROR')
    db.assert_('CORPORATION', 'TRANSFEREE')

    # TRANSFEREE voting stock — TRANSFEROR holds 100% at T1
    db.assert_('ISSUE', 'TRANSFEREE', 'S-C')
    db.assert_('STOCK', 'S-C')
    db.assert_('VOTING', 'S-C')
    db.assert_('COMMON', 'S-C')
    db.assert_('PIECE-OF', 'P-C', 'S-C')
    db.assert_('NSHARES', 'P-C', 100)
    db.assert_('OWN', 'TRANSFEROR', 'P-C', 'T1')

    # TRANSFEROR's operating property (not stock — PROP-CLASS has no STOCK assertion)
    db.assert_('PIECE-OF', 'PROP-P', 'PROP-CLASS')
    db.assert_('NSHARES', 'PROP-P', 1000)
    db.assert_('OWN', 'TRANSFEROR', 'PROP-P', 'T0')

    # TRANSFEROR transfers property to TRANSFEREE at T1
    assert_expand(db, 'TRANS', 'TRANSFEROR', 'PROP-P', 'TRANSFEROR', 'TRANSFEREE', 'T1')


@pytest.fixture
def db() -> Database:
    return Database()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered(self):
        assert 'D-REORGANIZATION' in ABSTRACT_THEOREMS

    def test_callable(self):
        assert callable(ABSTRACT_THEOREMS['D-REORGANIZATION'])


# ---------------------------------------------------------------------------
# Basic success
# ---------------------------------------------------------------------------

class TestBasicSuccess:
    def test_succeeds_with_property_transfer_and_control(self, db):
        _setup_basic_d_reorg(db)
        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert len(results) == 1

    def test_ground_args_yield_empty_binding(self, db):
        _setup_basic_d_reorg(db)
        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert results == [{}]

    def test_multiple_property_transfers_deduplicated(self, db):
        """Two TRANS entries from TRANSFEROR to TRANSFEREE at the same time yield one result."""
        db.assert_('CORPORATION', 'TRANSFEROR')
        db.assert_('CORPORATION', 'TRANSFEREE')

        db.assert_('ISSUE', 'TRANSFEREE', 'S-C')
        db.assert_('STOCK', 'S-C')
        db.assert_('VOTING', 'S-C')
        db.assert_('COMMON', 'S-C')
        db.assert_('PIECE-OF', 'P-C', 'S-C')
        db.assert_('NSHARES', 'P-C', 100)
        db.assert_('OWN', 'TRANSFEROR', 'P-C', 'T1')

        db.assert_('PIECE-OF', 'PROP-P1', 'PROP-CLASS-1')
        db.assert_('NSHARES', 'PROP-P1', 500)
        db.assert_('OWN', 'TRANSFEROR', 'PROP-P1', 'T0')

        db.assert_('PIECE-OF', 'PROP-P2', 'PROP-CLASS-2')
        db.assert_('NSHARES', 'PROP-P2', 500)
        db.assert_('OWN', 'TRANSFEROR', 'PROP-P2', 'T0')

        assert_expand(db, 'TRANS', 'TRANSFEROR', 'PROP-P1', 'TRANSFEROR', 'TRANSFEREE', 'T1')
        assert_expand(db, 'TRANS', 'TRANSFEROR', 'PROP-P2', 'TRANSFEROR', 'TRANSFEREE', 'T1')

        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Transferor is not a Corporation
# ---------------------------------------------------------------------------

class TestNotCorporation:
    def test_fails_when_transferor_not_corporation(self, db):
        _setup_basic_d_reorg(db)
        db.erase('CORPORATION', 'TRANSFEROR')

        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Transferred object is stock (not property)
# ---------------------------------------------------------------------------

class TestTransferIsStock:
    def test_fails_when_transferred_object_is_stock_not_property(self, db):
        """TRANSFEROR transfers a stock piece (not an asset) to TRANSFEREE → no D-Reorg."""
        db.assert_('CORPORATION', 'TRANSFEROR')
        db.assert_('CORPORATION', 'TRANSFEREE')

        # TRANSFEREE voting stock — TRANSFEROR controls TRANSFEREE
        db.assert_('ISSUE', 'TRANSFEREE', 'S-C')
        db.assert_('STOCK', 'S-C')
        db.assert_('VOTING', 'S-C')
        db.assert_('COMMON', 'S-C')
        db.assert_('PIECE-OF', 'P-C', 'S-C')
        db.assert_('NSHARES', 'P-C', 100)
        db.assert_('OWN', 'TRANSFEROR', 'P-C', 'T0')

        # TRANSFEROR also holds stock in a third corp
        db.assert_('ISSUE', 'THIRD-CORP', 'S-T')
        db.assert_('STOCK', 'S-T')
        db.assert_('PIECE-OF', 'P-T', 'S-T')
        db.assert_('NSHARES', 'P-T', 50)
        db.assert_('OWN', 'TRANSFEROR', 'P-T', 'T0')

        # TRANSFEROR transfers that stock piece (not property) to TRANSFEREE
        assert_expand(db, 'TRANS', 'TRANSFEROR', 'P-T', 'TRANSFEROR', 'TRANSFEREE', 'T1')
        # Stock ownership of TRANSFEREE at T1 for CONTROL check
        db.assert_('OWN', 'TRANSFEROR', 'P-C', 'T1')

        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert results == []

    def test_fails_when_no_trans_from_transferor_exists(self, db):
        """No TRANS at all → no asset transfer found → no D-Reorg."""
        db.assert_('CORPORATION', 'TRANSFEROR')
        db.assert_('CORPORATION', 'TRANSFEREE')
        # No TRANS entries
        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Transferor does not control transferee
# ---------------------------------------------------------------------------

class TestNoControl:
    def test_fails_when_transferor_does_not_control_transferee(self, db):
        """Asset transfer exists but TRANSFEROR owns none of TRANSFEREE's stock → no control."""
        db.assert_('CORPORATION', 'TRANSFEROR')
        db.assert_('CORPORATION', 'TRANSFEREE')

        # TRANSFEREE has voting stock but TRANSFEROR owns none of it
        db.assert_('ISSUE', 'TRANSFEREE', 'S-C')
        db.assert_('STOCK', 'S-C')
        db.assert_('VOTING', 'S-C')
        db.assert_('COMMON', 'S-C')
        db.assert_('PIECE-OF', 'P-C', 'S-C')
        db.assert_('NSHARES', 'P-C', 100)
        # Note: NO OWN assertion — TRANSFEROR holds 0% of TRANSFEREE

        db.assert_('PIECE-OF', 'PROP-P', 'PROP-CLASS')
        db.assert_('NSHARES', 'PROP-P', 1000)
        db.assert_('OWN', 'TRANSFEROR', 'PROP-P', 'T0')

        assert_expand(db, 'TRANS', 'TRANSFEROR', 'PROP-P', 'TRANSFEROR', 'TRANSFEREE', 'T1')

        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert results == []

    def test_fails_when_control_is_below_80_percent(self, db):
        """TRANSFEROR owns 79% of TRANSFEREE → below threshold → no D-Reorg."""
        db.assert_('CORPORATION', 'TRANSFEROR')
        db.assert_('CORPORATION', 'TRANSFEREE')

        db.assert_('ISSUE', 'TRANSFEREE', 'S-C')
        db.assert_('STOCK', 'S-C')
        db.assert_('VOTING', 'S-C')
        db.assert_('COMMON', 'S-C')

        db.assert_('PIECE-OF', 'P-C1', 'S-C')
        db.assert_('NSHARES', 'P-C1', 79)
        db.assert_('OWN', 'TRANSFEROR', 'P-C1', 'T1')

        db.assert_('PIECE-OF', 'P-C2', 'S-C')
        db.assert_('NSHARES', 'P-C2', 21)
        db.assert_('OWN', 'OTHER', 'P-C2', 'T1')

        db.assert_('PIECE-OF', 'PROP-P', 'PROP-CLASS')
        db.assert_('NSHARES', 'PROP-P', 1000)
        db.assert_('OWN', 'TRANSFEROR', 'PROP-P', 'T0')

        assert_expand(db, 'TRANS', 'TRANSFEROR', 'PROP-P', 'TRANSFEROR', 'TRANSFEREE', 'T1')

        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Variable patterns
# ---------------------------------------------------------------------------

class TestVariablePatterns:
    def test_variable_transferor(self, db):
        _setup_basic_d_reorg(db)
        results = list(goal_abstract(db, 'D-REORGANIZATION', '?A', 'TRANSFEREE', 'T1'))
        assert len(results) == 1
        assert results[0]['A'] == 'TRANSFEROR'

    def test_variable_transferee(self, db):
        _setup_basic_d_reorg(db)
        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', '?C', 'T1'))
        assert len(results) == 1
        assert results[0]['C'] == 'TRANSFEREE'

    def test_variable_time(self, db):
        _setup_basic_d_reorg(db)
        results = list(goal_abstract(db, 'D-REORGANIZATION', 'TRANSFEROR', 'TRANSFEREE', '?T'))
        assert len(results) == 1
        assert results[0]['T'] == 'T1'

    def test_all_variables(self, db):
        _setup_basic_d_reorg(db)
        results = list(goal_abstract(db, 'D-REORGANIZATION', '?A', '?C', '?T'))
        assert len(results) == 1
        r = results[0]
        assert r['A'] == 'TRANSFEROR'
        assert r['C'] == 'TRANSFEREE'
        assert r['T'] == 'T1'


# ---------------------------------------------------------------------------
# Direct DB bypass
# ---------------------------------------------------------------------------

class TestDirectDBBypass:
    def test_direct_entry_returned_without_running_theorem(self, db):
        db.assert_('D-REORGANIZATION', 'A', 'C', 'T0')
        results = list(goal_abstract(db, 'D-REORGANIZATION', 'A', 'C', 'T0'))
        assert results == [{}]

    def test_direct_entry_with_variable(self, db):
        db.assert_('D-REORGANIZATION', 'A', 'C', 'T0')
        results = list(goal_abstract(db, 'D-REORGANIZATION', '?A', 'C', 'T0'))
        assert results == [{'A': 'A'}]


# ---------------------------------------------------------------------------
# Wrong arity
# ---------------------------------------------------------------------------

class TestWrongArity:
    def test_zero_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['D-REORGANIZATION'](db)) == []

    def test_two_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['D-REORGANIZATION'](db, 'A', 'C')) == []

    def test_four_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['D-REORGANIZATION'](db, 'A', 'C', 'T', 'EXTRA')) == []


# ---------------------------------------------------------------------------
# Phellis-style case (CLAUDE.md §5.5, Query 4)
# ---------------------------------------------------------------------------

class TestPhellisStyle:
    def _setup(self, db: Database) -> None:
        """
        Simplified Phellis D-Reorganization:
          - NEW-JERSEY transfers its operating assets (PHE26) to DELAWARE.
          - DELAWARE issues its common voting stock (PHE31) to NEW-JERSEY.
          - After T1: NJ owns PHE31 (DE-COMMON, voting) → NJ controls DELAWARE.
          - D-Reorg(NJ, DELAWARE, T1) should succeed.
          - D-Reorg(DELAWARE, NJ, T1) should fail — DE transfers stock, not property,
            to NJ; and NJ has no stock issued so DE cannot control NJ.
        """
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')

        # NJ's operating assets — NJ-ASSETS has no STOCK assertion → it is property
        db.assert_('PIECE-OF', 'PHE26', 'NJ-ASSETS')
        db.assert_('NSHARES', 'PHE26', 1000)
        db.assert_('OWN', 'NEW-JERSEY', 'PHE26', 'T0')

        # DELAWARE's common voting stock
        db.assert_('ISSUE', 'DELAWARE', 'DE-COMMON')
        db.assert_('STOCK', 'DE-COMMON')
        db.assert_('VOTING', 'DE-COMMON')
        db.assert_('COMMON', 'DE-COMMON')
        db.assert_('PIECE-OF', 'PHE31', 'DE-COMMON')
        db.assert_('NSHARES', 'PHE31', 500)
        db.assert_('OWN', 'DELAWARE', 'PHE31', 'T0')

        # NJ transfers its assets to DELAWARE
        assert_expand(db, 'TRANS', 'NEW-JERSEY', 'PHE26', 'NEW-JERSEY', 'DELAWARE', 'T1')
        # DELAWARE issues its common stock to NJ (NJ now controls DELAWARE at T1)
        assert_expand(db, 'TRANS', 'DELAWARE', 'PHE31', 'DELAWARE', 'NEW-JERSEY', 'T1')

    def test_nj_transferor_delaware_transferee_succeeds(self, db):
        """
        D-Reorg(NJ, DELAWARE): NJ transfers assets (PHE26, not stock) to DE;
        NJ controls DELAWARE at T1 (owns 100% of DE-COMMON via PHE31) → succeeds.
        """
        self._setup(db)
        results = list(goal_abstract(
            db, 'D-REORGANIZATION', 'NEW-JERSEY', 'DELAWARE', '?T',
        ))
        assert len(results) == 1
        assert results[0]['T'] == 'T1'

    def test_delaware_transferor_nj_transferee_fails(self, db):
        """
        D-Reorg(DELAWARE, NJ): DELAWARE transfers PHE31 (DE-COMMON stock piece,
        not property) to NJ — fails the property filter.  NJ also has no stock
        issued so DELAWARE could not control NJ regardless.
        """
        self._setup(db)
        results = list(goal_abstract(
            db, 'D-REORGANIZATION', 'DELAWARE', 'NEW-JERSEY', '?T',
        ))
        assert results == []
