"""
End-to-end assertions for the Phellis case (United States v. Phellis).

Loads the Phellis fact database from main/cases/phellis.py and runs
goal_abstract queries against it, comparing results to the expected
outcomes in main/cases/phellis_expected.py.

CLAUDE.md §5.5 defines the four queries and their expected results:
  Query 1: B-Reorg(DE, NJ)  → fails
  Query 2: B-Reorg(NJ, DE)  → fails (assets given, not NJ voting stock)
  Query 3: C-Reorg(?, ?)    → succeeds: acquirer=DE, acquired=NJ
  Query 4: D-Reorg(?, ?)    → succeeds: transferor=NJ, transferee=DE

Additional assertions:
  - CONTROL(NJ, DE, T1) → true (NJ holds 100% DE voting stock before distribution)
  - STOCKHOLDER(PHELLIS, DE, T2) → true (Phellis receives DE common shares
    via the 2-for-1 distribution at T2)

Two fixtures are used because SPLITPIECE (called inside DISTRIBUTE) permanently
reduces NSHARES(PHE31) to 0, which would cause CONTROL(NJ, DE, T1) to fail if
both events co-existed in the same database.  reorg_db stops at T1; full_db
continues through T2.
"""
import pytest

from main.database import Database
from main.theorems.base import goal_abstract
import main.theorems.stockholder  # noqa: F401 — registers STOCKHOLDER
import main.theorems.control      # noqa: F401 — registers CONTROL
import main.theorems.trans        # noqa: F401 — registers TRANS, SPLITPIECE
import main.theorems.distribute   # noqa: F401 — registers DISTRIBUTE
import main.theorems.b_reorg      # noqa: F401 — registers B-REORGANIZATION
import main.theorems.c_reorg      # noqa: F401 — registers C-REORGANIZATION
import main.theorems.d_reorg      # noqa: F401 — registers D-REORGANIZATION

from main.cases.phellis import build_phellis_reorg_db, build_phellis_db
import main.cases.phellis_expected as expected


@pytest.fixture(scope='module')
def reorg_db() -> Database:
    """DB through T1 reorganization events only (no distribution).

    B/C/D-Reorg and CONTROL queries use this fixture so that the
    pre-distribution NSHARES counts are intact.
    """
    return build_phellis_reorg_db()


@pytest.fixture(scope='module')
def full_db() -> Database:
    """DB including the T2 distribution event.

    Post-distribution queries (Phellis as DE stockholder) use this fixture.
    CONTROL(NJ, DE, T1) does NOT hold here because SPLITPIECE has reduced
    NSHARES(PHE31) to 0.
    """
    return build_phellis_db()


# ---------------------------------------------------------------------------
# B-Reorganization
# ---------------------------------------------------------------------------

class TestBReorganization:
    def test_delaware_acquires_nj_fails(self, reorg_db):
        """
        B-Reorg(DE, NJ): DELAWARE never acquires NJ stock in any TRANS,
        so CONTROL(DE, NJ) cannot be established → no B-Reorg.
        """
        results = list(goal_abstract(reorg_db, 'B-REORGANIZATION', 'DELAWARE', 'NEW-JERSEY', '?T'))
        assert bool(results) is expected.B_REORG_DELAWARE_ACQUIRES_NJ

    def test_nj_acquires_delaware_fails(self, reorg_db):
        """
        B-Reorg(NJ, DE): NJ controls DE ✓ and NJ received DE stock ✓,
        but NJ gave PHE26 (assets, not NJ voting stock) to DE → solely-
        for-voting-stock fails → no B-Reorg.
        """
        results = list(goal_abstract(reorg_db, 'B-REORGANIZATION', 'NEW-JERSEY', 'DELAWARE', '?T'))
        assert bool(results) is expected.B_REORG_NJ_ACQUIRES_DELAWARE


# ---------------------------------------------------------------------------
# C-Reorganization
# ---------------------------------------------------------------------------

class TestCReorganization:
    def test_c_reorg_succeeds(self, reorg_db):
        """C-Reorg exists in the Phellis database."""
        results = list(goal_abstract(reorg_db, 'C-REORGANIZATION', '?A', '?C', '?T'))
        assert len(results) == 1

    def test_c_reorg_acquirer(self, reorg_db):
        """DELAWARE is the acquirer (receives NJ assets in exchange for DE voting stock)."""
        results = list(goal_abstract(reorg_db, 'C-REORGANIZATION', '?A', '?C', '?T'))
        assert results[0]['A'] == expected.C_REORG_ACQUIRER

    def test_c_reorg_acquired(self, reorg_db):
        """NEW-JERSEY is the acquired party (transfers assets to DELAWARE)."""
        results = list(goal_abstract(reorg_db, 'C-REORGANIZATION', '?A', '?C', '?T'))
        assert results[0]['C'] == expected.C_REORG_ACQUIRED

    def test_c_reorg_time_is_t1(self, reorg_db):
        """C-Reorg is found at T1 (the asset-transfer event time)."""
        results = list(goal_abstract(reorg_db, 'C-REORGANIZATION', '?A', '?C', '?T'))
        assert results[0]['T'] == 'T1'

    def test_c_reorg_ground_delaware_nj_succeeds(self, reorg_db):
        """Ground query C-Reorg(DE, NJ, T1) returns a match."""
        results = list(goal_abstract(reorg_db, 'C-REORGANIZATION', 'DELAWARE', 'NEW-JERSEY', 'T1'))
        assert len(results) == 1

    def test_c_reorg_reversed_nj_delaware_fails(self, reorg_db):
        """C-Reorg(NJ, DE): DE transferred stock (not property) to NJ → fails."""
        results = list(goal_abstract(reorg_db, 'C-REORGANIZATION', 'NEW-JERSEY', 'DELAWARE', '?T'))
        assert results == []


# ---------------------------------------------------------------------------
# D-Reorganization
# ---------------------------------------------------------------------------

class TestDReorganization:
    def test_d_reorg_succeeds(self, reorg_db):
        """D-Reorg (partial) exists in the Phellis database."""
        results = list(goal_abstract(reorg_db, 'D-REORGANIZATION', '?A', '?C', '?T'))
        assert len(results) == 1

    def test_d_reorg_transferor(self, reorg_db):
        """NEW-JERSEY is the transferor (transfers assets to DE which it controls)."""
        results = list(goal_abstract(reorg_db, 'D-REORGANIZATION', '?A', '?C', '?T'))
        assert results[0]['A'] == expected.D_REORG_TRANSFEROR

    def test_d_reorg_transferee(self, reorg_db):
        """DELAWARE is the transferee (receives NJ assets; controlled by NJ after)."""
        results = list(goal_abstract(reorg_db, 'D-REORGANIZATION', '?A', '?C', '?T'))
        assert results[0]['C'] == expected.D_REORG_TRANSFEREE

    def test_d_reorg_time_is_t1(self, reorg_db):
        """D-Reorg is found at T1 (the asset-transfer event time)."""
        results = list(goal_abstract(reorg_db, 'D-REORGANIZATION', '?A', '?C', '?T'))
        assert results[0]['T'] == 'T1'

    def test_d_reorg_reversed_delaware_nj_fails(self, reorg_db):
        """D-Reorg(DE, NJ): DE transfers stock (not property) to NJ → fails."""
        results = list(goal_abstract(reorg_db, 'D-REORGANIZATION', 'DELAWARE', 'NEW-JERSEY', '?T'))
        assert results == []


# ---------------------------------------------------------------------------
# Control
# ---------------------------------------------------------------------------

class TestControl:
    def test_nj_controls_delaware_at_t1(self, reorg_db):
        """
        At T1, NJ holds 100% of DE's voting stock (PHE27 debenture and PHE30
        common classes, 1000 + 500 = 1500 shares all owned by NJ) →
        CONTROL(NJ, DE, T1) holds.
        """
        results = list(goal_abstract(
            reorg_db, 'CONTROL', 'NEW-JERSEY', 'DELAWARE',
            expected.NJ_CONTROLS_DELAWARE_AT,
        ))
        assert bool(results) is expected.NJ_CONTROLS_DELAWARE

    def test_delaware_does_not_control_nj(self, reorg_db):
        """DELAWARE owns no NJ stock → CONTROL(DE, NJ) never holds."""
        results = list(goal_abstract(reorg_db, 'CONTROL', 'DELAWARE', 'NEW-JERSEY', '?T'))
        assert results == []


# ---------------------------------------------------------------------------
# Post-distribution: Phellis as DE stockholder
# ---------------------------------------------------------------------------

class TestPostDistribution:
    def test_phellis_is_delaware_stockholder_at_t2(self, full_db):
        """
        After the 2-for-1 DISTRIBUTE at T2, Phellis holds 500 DE common shares
        → STOCKHOLDER(PHELLIS, DELAWARE, T2) holds.
        """
        results = list(goal_abstract(
            full_db, 'STOCKHOLDER', 'PHELLIS', 'DELAWARE',
            expected.PHELLIS_IS_DELAWARE_STOCKHOLDER_AT,
        ))
        assert bool(results) is expected.PHELLIS_IS_DELAWARE_STOCKHOLDER

    def test_phellis_de_shares_are_500(self, full_db):
        """
        Phellis's DE common piece has NSHARES = 500 (2 × 250 NJ common shares).
        The generated piece symbol is not known in advance; find it via OWN query.
        """
        t = expected.PHELLIS_IS_DELAWARE_STOCKHOLDER_AT
        phellis_de_pieces = full_db.query('OWN', 'PHELLIS', '?P', t)
        # Filter to pieces of DE common (PHE30)
        de_common_pieces = [
            b['P'] for b in phellis_de_pieces
            if full_db.query('PIECE-OF', b['P'], 'PHE30')
        ]
        assert len(de_common_pieces) == 1
        piece = de_common_pieces[0]
        n_res = full_db.query('NSHARES', piece, '?N')
        assert n_res and n_res[0]['N'] == 500
