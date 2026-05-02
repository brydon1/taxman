"""
Tests for main/theorems/c_reorg.py — C-REORGANIZATION abstract theorem.

C-Reorganization (§368(a)(1)(C)):
  Acquisition by one corporation (A) of substantially all the properties of
  another corporation (C), solely in exchange for all or part of A's voting
  stock.

Key structural constraints:
  - A must be a CORPORATION
  - A must receive property from C (TRANS where recip=A, obj is PIECE-OF a
    non-STOCK class — i.e. an asset, not stock of C)
  - All consideration given by A to C must be a piece of VOTING STOCK issued
    by A (solely-for-voting-stock requirement)
  - "Substantially all" test is partial: verified that A received property
    from C, but C's retained assets are not checked (CLAUDE.md §9)

Phellis case query (CLAUDE.md §5.5):
  - C-Reorg(Delaware, NJ) → succeeds: DE acquires NJ assets (PHE26),
    NJ receives DE common voting stock (PHE31 — stipulated voting)

Coverage:
  - Registration
  - Simple successful C-Reorg
  - Ground args yield empty binding
  - Multiple property transfers from C to A deduplicated to one result
  - Fails when A is not a CORPORATION
  - Fails when C transfers stock (not property) to A
  - Fails when no TRANS from C to A exists
  - Fails when consideration is non-voting stock of A
  - Fails when consideration includes both voting and non-voting stock of A
  - Fails when consideration is assets (not stock of A at all)
  - Fails when A gives nothing to C
  - Variable acquirer / target / time patterns
  - All three variables
  - Direct DB entry bypasses theorem
  - Wrong arity yields nothing
  - Phellis-style: Delaware acquirer, NJ target succeeds
"""
import pytest

from main.database import Database
from main.theorems.base import ABSTRACT_THEOREMS, goal_abstract, assert_expand
import main.theorems.trans    # noqa: F401 — registers TRANS, SPLITPIECE
import main.theorems.c_reorg  # noqa: F401 — registers C-REORGANIZATION


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _setup_acquirer_stock(db: Database, corp: str, stock_sym: str, piece: str, n: int,
                          *, voting: bool = True) -> None:
    """Set up a corporation with a single stock class and one treasury piece."""
    db.assert_('CORPORATION', corp)
    db.assert_('ISSUE', corp, stock_sym)
    db.assert_('STOCK', stock_sym)
    if voting:
        db.assert_('VOTING', stock_sym)
    db.assert_('COMMON', stock_sym)
    db.assert_('PIECE-OF', piece, stock_sym)
    db.assert_('NSHARES', piece, n)
    # No prior OWN — issued from treasury; TRANS erase is a no-op


def _setup_target_property(db: Database, corp: str, asset_class: str, piece: str,
                            n: int, time: str = 'T0') -> None:
    """Set up a corporation that owns a non-stock property piece."""
    db.assert_('CORPORATION', corp)
    # asset_class intentionally has no STOCK assertion → it is property
    db.assert_('PIECE-OF', piece, asset_class)
    db.assert_('NSHARES', piece, n)
    db.assert_('OWN', corp, piece, time)


def _setup_basic_c_reorg(db: Database) -> None:
    """
    Minimal successful C-Reorg:
      ACQUIRER receives TARGET's property (ASSET-P) from TARGET.
      ACQUIRER gives its own voting stock (P-A) to TARGET in exchange.
    """
    _setup_acquirer_stock(db, 'ACQUIRER', 'S-A', 'P-A', 100, voting=True)
    _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P', 1000)

    # TARGET transfers its property to ACQUIRER
    assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P', 'TARGET', 'ACQUIRER', 'T1')
    # ACQUIRER gives its voting stock to TARGET as consideration
    assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'TARGET', 'T1')


@pytest.fixture
def db() -> Database:
    return Database()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered(self):
        assert 'C-REORGANIZATION' in ABSTRACT_THEOREMS

    def test_callable(self):
        assert callable(ABSTRACT_THEOREMS['C-REORGANIZATION'])


# ---------------------------------------------------------------------------
# Basic success
# ---------------------------------------------------------------------------

class TestBasicSuccess:
    def test_succeeds_with_property_for_voting_stock(self, db):
        _setup_basic_c_reorg(db)
        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert len(results) == 1

    def test_ground_args_yield_empty_binding(self, db):
        _setup_basic_c_reorg(db)
        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == [{}]

    def test_multiple_property_pieces_same_exchange_deduplicated(self, db):
        """Two TRANS entries from TARGET to ACQUIRER at the same time yield one result."""
        _setup_acquirer_stock(db, 'ACQUIRER', 'S-A', 'P-A', 100, voting=True)
        _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P1', 500)
        _setup_target_property(db, 'TARGET', 'ASSET-CLASS-2', 'ASSET-P2', 500, time='T0')

        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P1', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P2', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'TARGET', 'T1')

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Acquirer is not a Corporation
# ---------------------------------------------------------------------------

class TestNotCorporation:
    def test_fails_when_acquirer_not_corporation(self, db):
        _setup_basic_c_reorg(db)
        db.erase('CORPORATION', 'ACQUIRER')

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Target transfers stock, not property
# ---------------------------------------------------------------------------

class TestTransferIsStock:
    def test_fails_when_target_transfers_stock_not_property(self, db):
        """C transfers its own stock to A — that is a B-Reorg scenario, not C-Reorg."""
        _setup_acquirer_stock(db, 'ACQUIRER', 'S-A', 'P-A', 100, voting=True)

        # TARGET with a stock class (not property)
        db.assert_('CORPORATION', 'TARGET')
        db.assert_('ISSUE', 'TARGET', 'S-C')
        db.assert_('STOCK', 'S-C')
        db.assert_('VOTING', 'S-C')
        db.assert_('PIECE-OF', 'P-C', 'S-C')
        db.assert_('NSHARES', 'P-C', 100)
        db.assert_('OWN', 'TARGET', 'P-C', 'T0')

        # TARGET transfers a stock piece to ACQUIRER
        assert_expand(db, 'TRANS', 'TARGET', 'P-C', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'TARGET', 'T1')

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_no_trans_to_acquirer(self, db):
        """No TRANS at all from TARGET → no C-Reorg."""
        _setup_acquirer_stock(db, 'ACQUIRER', 'S-A', 'P-A', 100, voting=True)
        _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P', 1000)
        # No assert_expand calls

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Consideration not solely voting stock of A
# ---------------------------------------------------------------------------

class TestNotSolelyVotingStock:
    def test_fails_when_consideration_is_nonvoting_stock(self, db):
        """A gives only non-voting stock to C → solely-for-voting-stock violated."""
        _setup_acquirer_stock(db, 'ACQUIRER', 'S-A-NV', 'P-A-NV', 100, voting=False)
        _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P', 1000)

        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A-NV', 'ACQUIRER', 'TARGET', 'T1')

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_consideration_includes_nonvoting_stock(self, db):
        """A gives voting + non-voting stock to C → mixed → solely-for-voting violated."""
        _setup_acquirer_stock(db, 'ACQUIRER', 'S-A', 'P-A', 80, voting=True)
        # Add a non-voting stock class for ACQUIRER
        db.assert_('ISSUE', 'ACQUIRER', 'S-A-NV')
        db.assert_('STOCK', 'S-A-NV')
        db.assert_('COMMON', 'S-A-NV')
        # No VOTING for S-A-NV
        db.assert_('PIECE-OF', 'P-A-NV', 'S-A-NV')
        db.assert_('NSHARES', 'P-A-NV', 20)

        _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P', 1000)

        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A', 'ACQUIRER', 'TARGET', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'P-A-NV', 'ACQUIRER', 'TARGET', 'T1')

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_consideration_is_assets_not_stock(self, db):
        """A gives operating assets (not stock) to C as consideration → fails."""
        db.assert_('CORPORATION', 'ACQUIRER')
        # ACQUIRER has its own property piece to give (not stock)
        db.assert_('PIECE-OF', 'ACQ-ASSET-P', 'ACQ-ASSET-CLASS')
        db.assert_('NSHARES', 'ACQ-ASSET-P', 50)

        _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P', 1000)

        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P', 'TARGET', 'ACQUIRER', 'T1')
        assert_expand(db, 'TRANS', 'ACQUIRER', 'ACQ-ASSET-P', 'ACQUIRER', 'TARGET', 'T1')

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []

    def test_fails_when_no_consideration_given_to_target(self, db):
        """TARGET transfers property to ACQUIRER but ACQUIRER gives TARGET nothing → fails."""
        _setup_acquirer_stock(db, 'ACQUIRER', 'S-A', 'P-A', 100, voting=True)
        _setup_target_property(db, 'TARGET', 'ASSET-CLASS', 'ASSET-P', 1000)

        assert_expand(db, 'TRANS', 'TARGET', 'ASSET-P', 'TARGET', 'ACQUIRER', 'T1')
        # No TRANS from ACQUIRER to TARGET

        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', 'T1'))
        assert results == []


# ---------------------------------------------------------------------------
# Variable patterns
# ---------------------------------------------------------------------------

class TestVariablePatterns:
    def test_variable_acquirer(self, db):
        _setup_basic_c_reorg(db)
        results = list(goal_abstract(db, 'C-REORGANIZATION', '?A', 'TARGET', 'T1'))
        assert len(results) == 1
        assert results[0]['A'] == 'ACQUIRER'

    def test_variable_target(self, db):
        _setup_basic_c_reorg(db)
        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', '?C', 'T1'))
        assert len(results) == 1
        assert results[0]['C'] == 'TARGET'

    def test_variable_time(self, db):
        _setup_basic_c_reorg(db)
        results = list(goal_abstract(db, 'C-REORGANIZATION', 'ACQUIRER', 'TARGET', '?T'))
        assert len(results) == 1
        assert results[0]['T'] == 'T1'

    def test_all_variables(self, db):
        _setup_basic_c_reorg(db)
        results = list(goal_abstract(db, 'C-REORGANIZATION', '?A', '?C', '?T'))
        assert len(results) == 1
        r = results[0]
        assert r['A'] == 'ACQUIRER'
        assert r['C'] == 'TARGET'
        assert r['T'] == 'T1'


# ---------------------------------------------------------------------------
# Direct DB bypass
# ---------------------------------------------------------------------------

class TestDirectDBBypass:
    def test_direct_entry_returned_without_running_theorem(self, db):
        db.assert_('C-REORGANIZATION', 'A', 'C', 'T0')
        results = list(goal_abstract(db, 'C-REORGANIZATION', 'A', 'C', 'T0'))
        assert results == [{}]

    def test_direct_entry_with_variable(self, db):
        db.assert_('C-REORGANIZATION', 'A', 'C', 'T0')
        results = list(goal_abstract(db, 'C-REORGANIZATION', '?A', 'C', 'T0'))
        assert results == [{'A': 'A'}]


# ---------------------------------------------------------------------------
# Wrong arity
# ---------------------------------------------------------------------------

class TestWrongArity:
    def test_zero_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['C-REORGANIZATION'](db)) == []

    def test_two_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['C-REORGANIZATION'](db, 'A', 'C')) == []

    def test_four_args_yields_nothing(self, db):
        assert list(ABSTRACT_THEOREMS['C-REORGANIZATION'](db, 'A', 'C', 'T', 'EXTRA')) == []


# ---------------------------------------------------------------------------
# Phellis-style case (CLAUDE.md §5.5, Query 3)
# ---------------------------------------------------------------------------

class TestPhellisStyle:
    def _setup(self, db):
        """
        Simplified Phellis C-Reorganization:
          - NEW-JERSEY transfers its operating assets to DELAWARE.
          - DELAWARE gives NJ its common voting stock in return.
          - C-Reorg(DELAWARE, NEW-JERSEY) should succeed.

        PHE26 = NJ's property piece (operating assets, not stock).
        PHE31 = Delaware common piece (voting stock).
        """
        db.assert_('CORPORATION', 'NEW-JERSEY')
        db.assert_('CORPORATION', 'DELAWARE')

        # NJ's operating assets — no STOCK assertion on NJ-ASSETS
        db.assert_('PIECE-OF', 'PHE26', 'NJ-ASSETS')
        db.assert_('NSHARES', 'PHE26', 1000)
        db.assert_('OWN', 'NEW-JERSEY', 'PHE26', 'T0')

        # Delaware's common voting stock
        db.assert_('ISSUE', 'DELAWARE', 'DE-COMMON')
        db.assert_('STOCK', 'DE-COMMON')
        db.assert_('VOTING', 'DE-COMMON')
        db.assert_('COMMON', 'DE-COMMON')
        db.assert_('PIECE-OF', 'PHE31', 'DE-COMMON')
        db.assert_('NSHARES', 'PHE31', 500)
        # PHE31 issued from treasury — no prior OWN needed

        # NJ transfers assets to DELAWARE
        assert_expand(db, 'TRANS', 'NEW-JERSEY', 'PHE26', 'NEW-JERSEY', 'DELAWARE', 'T1')
        # DELAWARE gives its common voting stock to NJ as consideration
        assert_expand(db, 'TRANS', 'DELAWARE', 'PHE31', 'DELAWARE', 'NEW-JERSEY', 'T1')

    def test_delaware_acquirer_nj_target_succeeds(self, db):
        """
        C-Reorg(DELAWARE, NEW-JERSEY): DELAWARE receives NJ property (PHE26, not stock),
        NJ receives DELAWARE voting stock (PHE31 = common, stipulated voting) — succeeds.
        """
        self._setup(db)
        results = list(goal_abstract(
            db, 'C-REORGANIZATION', 'DELAWARE', 'NEW-JERSEY', '?T',
        ))
        assert len(results) == 1
        assert results[0]['T'] == 'T1'

    def test_nj_acquirer_delaware_target_fails_no_nj_property_acquired(self, db):
        """
        C-Reorg(NEW-JERSEY, DELAWARE): NJ did not receive property from DELAWARE
        (DE transferred voting stock to NJ, not property) → no C-Reorg.
        """
        self._setup(db)
        results = list(goal_abstract(
            db, 'C-REORGANIZATION', 'NEW-JERSEY', 'DELAWARE', '?T',
        ))
        assert results == []
