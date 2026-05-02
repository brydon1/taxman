"""
United States v. Phellis, 257 U.S. 156 (1921) — Phellis case data.

This module constructs the TAXMAN database for the Phellis reorganization
(CLAUDE.md §8).  Call build_phellis_db() to obtain a fully populated Database
ready for querying with goal_abstract.

Symbol inventory (following CLAUDE.md §8 naming):
  PHE1  — NJ preferred stock class
  PHE2  — NJ common stock class (VOTING)
  PHE3  — NJ 5% mortgage bond class (BOND)
  PHE4  — NJ 4.5% 30-year bond class (BOND)
  PHE5  — Phellis's shareholding in NJ common (250 shares)
  PHE26 — NJ operating assets piece (non-stock property)
  PHE27 — DE 6% cumulative debenture stock class (VOTING, stipulated)
  PHE29 — DE debenture piece (transferred to NJ in the reorganization)
  PHE30 — DE common stock class (VOTING)
  PHE31 — DE common piece (distributed to NJ common holders 2-for-1)

Time tokens:
  T0 — initial state (pre-reorganization ownership)
  T1 — reorganization events (asset transfer, DE stock issuances)
  T2 — distribution event (NJ distributes DE common to NJ common holders)

Theorem modules TRANS and DISTRIBUTE are imported here so the expand handlers
are registered before assert_expand is called.  The querying theorems
(STOCKHOLDER, CONTROL, B/C/D-REORG) must be imported by the caller.
"""
from main.database import Database
from main.theorems.base import assert_expand

import main.theorems.trans      # noqa: F401 — registers TRANS, SPLITPIECE
import main.theorems.distribute  # noqa: F401 — registers DISTRIBUTE


def build_phellis_reorg_db() -> Database:
    """Build the Phellis database through the T1 reorganization events only.

    Returns the DB immediately after the three TRANS events (asset transfer,
    debenture issuance, common-stock issuance) at T1.  At this point:
      - OWN(NJ, PHE26, T0) is erased; OWN(DE, PHE26, T1) exists.
      - OWN(NJ, PHE29, T1) and OWN(NJ, PHE31, T1) exist (100% DE voting).
      - CONTROL(NJ, DE, T1) holds.

    The distribution event (T2) is NOT included.  Use build_phellis_db() to
    get the complete database including the T2 distribution.
    """
    db = Database()

    # ------------------------------------------------------------------
    # Corporations
    # ------------------------------------------------------------------
    db.assert_('CORPORATION', 'NEW-JERSEY')
    db.assert_('CORPORATION', 'DELAWARE')

    # ------------------------------------------------------------------
    # NEW-JERSEY stock and bond classes (initial state)
    # ------------------------------------------------------------------

    # PHE1 — NJ 6% preferred stock (not VOTING for our purposes)
    db.assert_('ISSUE', 'NEW-JERSEY', 'PHE1')
    db.assert_('STOCK', 'PHE1')
    db.assert_('PREFERRED', 'PHE1')

    # PHE2 — NJ common stock (VOTING)
    db.assert_('ISSUE', 'NEW-JERSEY', 'PHE2')
    db.assert_('STOCK', 'PHE2')
    db.assert_('COMMON', 'PHE2')
    db.assert_('VOTING', 'PHE2')

    # PHE3 — NJ 5% mortgage bonds (BOND, not STOCK)
    db.assert_('ISSUE', 'NEW-JERSEY', 'PHE3')
    db.assert_('BOND', 'PHE3')

    # PHE4 — NJ 4.5% 30-year bonds (BOND, not STOCK)
    db.assert_('ISSUE', 'NEW-JERSEY', 'PHE4')
    db.assert_('BOND', 'PHE4')

    # Phellis holds 250 shares of NJ common.
    # Asserted at T2 so that the DISTRIBUTE expand can find Phellis as a
    # holder of PHE2 when it queries OWN(?, PHE5, T2).
    db.assert_('PIECE-OF', 'PHE5', 'PHE2')
    db.assert_('NSHARES', 'PHE5', 250)
    db.assert_('OWN', 'PHELLIS', 'PHE5', 'T2')

    # ------------------------------------------------------------------
    # NEW-JERSEY operating assets (non-stock property)
    # ------------------------------------------------------------------

    # PHE26 — NJ's operating assets (~$120M book value).
    # NJ-ASSETS has no STOCK assertion → PHE26 is treated as property by
    # _is_property_of in the C-Reorg and D-Reorg theorems.
    db.assert_('PIECE-OF', 'PHE26', 'NJ-ASSETS')
    db.assert_('NSHARES', 'PHE26', 1)
    db.assert_('OWN', 'NEW-JERSEY', 'PHE26', 'T0')

    # ------------------------------------------------------------------
    # DELAWARE stock classes and treasury holdings (initial state)
    # ------------------------------------------------------------------

    # PHE27 — DE 6% cumulative debenture stock class (VOTING, stipulated)
    db.assert_('ISSUE', 'DELAWARE', 'PHE27')
    db.assert_('STOCK', 'PHE27')
    db.assert_('DEBENTURE', 'PHE27')
    db.assert_('VOTING', 'PHE27')    # stipulated voting per CLAUDE.md §5.5

    # PHE29 — DE debenture piece (all held by DELAWARE at T0)
    db.assert_('PIECE-OF', 'PHE29', 'PHE27')
    db.assert_('NSHARES', 'PHE29', 1000)
    db.assert_('OWN', 'DELAWARE', 'PHE29', 'T0')

    # PHE30 — DE common stock class (VOTING)
    db.assert_('ISSUE', 'DELAWARE', 'PHE30')
    db.assert_('STOCK', 'PHE30')
    db.assert_('COMMON', 'PHE30')
    db.assert_('VOTING', 'PHE30')

    # PHE31 — DE common piece (500 shares = 2× Phellis's 250 NJ common)
    db.assert_('PIECE-OF', 'PHE31', 'PHE30')
    db.assert_('NSHARES', 'PHE31', 500)
    db.assert_('OWN', 'DELAWARE', 'PHE31', 'T0')

    # ------------------------------------------------------------------
    # Reorganization events at T1
    # (October 1, 1915 — all treated as simultaneous)
    # ------------------------------------------------------------------

    # Event 1: NJ transfers all operating assets (PHE26) to DELAWARE.
    #   Pre:  OWN(NJ, PHE26, T0)
    #   Post: OWN(DE, PHE26, T1)
    assert_expand(db, 'TRANS', 'NEW-JERSEY', 'PHE26', 'NEW-JERSEY', 'DELAWARE', 'T1')

    # Event 2: DELAWARE issues debenture stock (PHE29) to NJ.
    #   Pre:  OWN(DE, PHE29, T0)
    #   Post: OWN(NJ, PHE29, T1)
    assert_expand(db, 'TRANS', 'DELAWARE', 'PHE29', 'DELAWARE', 'NEW-JERSEY', 'T1')

    # Event 3: DELAWARE issues common stock (PHE31) to NJ.
    #   Pre:  OWN(DE, PHE31, T0)
    #   Post: OWN(NJ, PHE31, T1)
    assert_expand(db, 'TRANS', 'DELAWARE', 'PHE31', 'DELAWARE', 'NEW-JERSEY', 'T1')

    # At T1, NJ owns 100% of DE's voting stock (PHE27 and PHE30 classes).
    # → CONTROL(NJ, DE, T1) holds.

    return db


def build_phellis_db() -> Database:
    """Build the complete Phellis database, including the T2 distribution.

    Extends the T1 reorganization database with:
      - OWN(PHELLIS, PHE5, T2) — Phellis still holds NJ common at T2.
      - DISTRIBUTION-RULE(PHE31, N-FOR-ONE, 2, PHE2) — 2-for-1 rule.
      - DISTRIBUTE at T2 — creates a new piece of 500 DE common shares
        for Phellis and reduces NSHARES(PHE31) to 0 via SPLITPIECE.

    WARNING: the SPLITPIECE permanently alters NSHARES(PHE31) to 0 and
    adds a new PIECE-OF entry for PHE30.  Consequently _check_control at
    T1 sees the post-distribution share counts and CONTROL(NJ, DE, T1)
    no longer holds in this database.  Use build_phellis_reorg_db() for
    queries that require the pre-distribution state.
    """
    db = build_phellis_reorg_db()

    # Phellis still holds NJ common at T2 (no intervening transfer).
    db.assert_('OWN', 'PHELLIS', 'PHE5', 'T2')

    # Distribution rule: 2 DE common shares per 1 NJ common share held.
    db.assert_('DISTRIBUTION-RULE', 'PHE31', 'N-FOR-ONE', 2, 'PHE2')

    # Event 4: NJ distributes DE common stock (PHE31) 2-for-1 to NJ
    # common stockholders at T2.  Phellis receives 2 × 250 = 500 shares.
    assert_expand(
        db,
        'DISTRIBUTE',
        'NEW-JERSEY',   # subject
        'PHE31',        # object (the DE common piece being distributed)
        'NEW-JERSEY',   # owner (NJ holds PHE31 at T1)
        'NEW-JERSEY',   # recipient_corp (NJ common holders receive it)
        'T2',           # time
    )

    return db
