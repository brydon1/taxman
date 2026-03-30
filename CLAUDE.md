# TAXMAN: Implementation Reference

> McCarty, L. Thorne. "Reflections on TAXMAN: An Experiment in Artificial Intelligence and Legal Reasoning."
> *Datenverarbeitung im Recht* Band 5, Heft 4/1976. J. Schweitzer Verlag Berlin.
> Written in micro-Planner (a subset of Lisp). Runs on PDP-10. ~450 lines of code + ~200 lines case description.

---

## 0. General Instructions
Always read AGENTS.md and DECISIONS.md before starting any task. As you implement code for a task, update the DECISIONS.md file with any pertinent design decisions to keep in mind for future development.

## 1. Core Data Model

### 1.1 Propositions as Lists

Every fact is a parenthesized list: `(PREDICATE ARG1 ARG2 ...)`.
- First element = **predicate** (one-place, two-place, etc.)
- Remaining elements = **objects** (atoms or internally generated symbols)

```lisp
; Basic facts
(CORPORATION NEW-JERSEY)
(CORPORATION DELAWARE)
(ISSUE NEW-JERSEY S1)       ; NJ has issued stock class S1
(STOCK S1)
(COMMON S1)
(PIECE-OF P1 S1)            ; P1 is a shareholding piece of S1
(NSHARES P1 100)            ; P1 represents 100 shares
(OWN PHELLIS P1)            ; Phellis owns P1
```

### 1.2 Nominalization Convention

Whenever a concept must be treated as an **object** (to hang further predicates on it),
generate a fresh internal symbol and assert two lists:

```lisp
; "NJ has issued stock" → can't say more about Stock itself
; Solution: generate symbol S1
(ISSUE NEW-JERSEY S1)
(STOCK S1)
; Now attach attributes to S1
(COMMON S1)
(VOTING S1)
```

Same for ownership interests — Phellis doesn't own S1 directly; he owns a *piece-of* S1:

```lisp
(PIECE-OF P1 S1)
(NSHARES P1 100)
(OWN PHELLIS P1)
```

### 1.3 Semantic Network View

The list set above is isomorphic to a labeled directed graph:

```
CORPORATION──▶[NJ]──ISSUE──▶[S1]──STOCK
                              │
                            COMMON
                              │
                          PIECE-OF──▶[P1]──NSHARES:100
                                          │
                                         OWN
                                          │
                                       [PHELLIS]
```

Nodes = objects (circles). Edges = predicates with argument-position labels (1, 2, ...).

### 1.4 Time-Indexed Propositions

Append a **state/time token** as the final argument to any proposition that may change:

```lisp
(OWN PHELLIS P1 T4)       ; Phellis owns P1 at time T4
(OWN PHELLIS P1)          ; Phellis owns P1 at ALL times in scope
```

Internally, each proposition stores a list of time periods during which it is "true".
`Assert`, `Erase`, and `Goal` are modified to check/update these time-period lists.

---

## 2. Primitive Operations

### 2.1 Assert

Store and index a list in the database:

```lisp
(Assert (CORPORATION NEW-JERSEY))
; → stores (CORPORATION NEW-JERSEY) at a retrievable location
; → makes it "operationally true"
```

Time-indexed form:

```lisp
(Assert (OWN PHELLIS P1 T4))
```

### 2.2 Erase

Remove a list from the database:

```lisp
(Erase (CORPORATION NEW-JERSEY))
; → list no longer retrievable → "operationally false"
```

### 2.3 Goal

Retrieve / verify propositions. Three modes:

```lisp
; Mode 1 — Verification (all arguments ground)
(Goal (CORPORATION NEW-JERSEY))
; → T if list exists, Nil otherwise

; Mode 2 — Existential search (anonymous variable '?')
(Goal (CORPORATION ?))
; → first match, e.g. (CORPORATION NEW-JERSEY), or Nil

; Mode 3 — Variable binding
(Goal (CORPORATION ?X))
; → binds X ← NEW-JERSEY on success

; Mode 4 — Enumerate all matches
(Find All (CORPORATION ?))
; → ((CORPORATION NEW-JERSEY) (CORPORATION DELAWARE))
```

---

## 3. Compound Operations

### 3.1 Prog — Sequential Search with Backtracking

```lisp
(PROG (var1 var2 ...)
  (GOAL expr1)
  (GOAL expr2)
  ...
  (GOAL exprN))
```

- Variables are assigned as each Goal succeeds.
- If a later Goal fails, **backtrack** to the previous Goal and try the next match.
- Equivalent to a parallel search implemented as iterative trial-and-error.

**Example — "Phellis is a stockholder of New-Jersey":**

```lisp
(PROG (S P)
  (GOAL (ISSUE NEW-JERSEY ?S))   ; bind S ← S1
  (GOAL (STOCK ?S))              ; verify S1 is a stock
  (GOAL (PIECE-OF ?P ?S))        ; bind P ← P1
  (GOAL (OWN PHELLIS ?P)))       ; verify Phellis owns P1
; → succeeds: S=S1, P=P1
```

### 3.2 Theorem Abstract — Deductive Rule (Abstraction)

Wraps a Prog into a named, reusable concept definition:

```lisp
(THEOREM ABSTRACT (O C S P)
  (STOCKHOLDER ?O ?C)            ; ← pattern to match
  (GOAL (ISSUE ?C ?S))
  (GOAL (STOCK ?S))
  (GOAL (PIECE-OF ?P ?S))
  (GOAL (OWN ?O ?P)))
```

- Triggered when `(Goal (STOCKHOLDER ?O ?C) Abstract)` is called.
- First searches DB for a direct `(STOCKHOLDER ...)` assertion.
- On miss, finds this theorem, unifies pattern, runs the Goal sequence.

**Usage:**

```lisp
(Goal (STOCKHOLDER PHELLIS NEW-JERSEY) Abstract)
; → runs Prog body with O=PHELLIS, C=NEW-JERSEY

(Goal (STOCKHOLDER ?O NEW-JERSEY) Abstract)
; → finds all stockholders of NJ

(Find All (STOCKHOLDER ? NEW-JERSEY) Abstract)
; → returns list of all stockholder relationships
```

### 3.3 Theorem Expand — Generative Rule (Expansion)

Reverse of Abstract: given a high-level assertion, **generate** low-level DB entries.

```lisp
(THEOREM EXPAND (O C ...)
  (STOCKHOLDER ?O ?C)
  <body of ASSERTions>)
```

Triggered by:

```lisp
(Assert (STOCKHOLDER PHELLIS NEW-JERSEY) Expand)
; → runs expansion body, creating (ISSUE ...), (STOCK ...), (PIECE-OF ...), (OWN ...) entries
; → program chooses which concrete expansions make sense given existing DB context
```

**Ambiguity rule:** If multiple expansions are possible (e.g. multiple existing stock classes),
the program flags the ambiguity in the network rather than choosing arbitrarily.
The system can back up and correct mistaken expansions later.

---

## 4. Event Descriptions

### 4.1 Primitive Event: Trans

Models a single ownership transfer:

```lisp
(Trans <subject> <object> <owner> <recipient> <time>)
; "subject transfers object from owner to recipient at time"
```

**Expand theorem for Trans:**

```lisp
(THEOREM EXPAND (S X O R T  T0=(LAST STATE))
  (TRANS ?S ?X ?O ?R ?T)
  (IF (GOAL (OWN ?O ?X ?T0))
    THEN
      (ERASE  (OWN ?O ?X ?T))
      (ASSERT (OWN ?R ?X ?T))))
```

**Example — "Phellis transfers P1 to Delaware":**

```lisp
(Assert (Trans Phellis P1 Phellis Delaware <time>) Expand)
; Pre-state: (OWN PHELLIS P1 T0)
; Post-state: (OWN DELAWARE P1 T1)
;             (OWN PHELLIS P1 T0) erased
```

### 4.2 Partial Transfer: Splitpiece

Split P1 into two pieces before transferring only part:

```lisp
(PROG (P = (GEN))
  (ASSERT (NSHARES ?P 20))
  (ASSERT (SPLITPIECE ?P P1 <time>) EXPAND)
  (ASSERT (TRANS PHELLIS ?P PHELLIS DELAWARE <time>) EXPAND))
; → creates new piece ?P of size 20 shares
; → adjusts P1 to reflect remaining shares
; → transfers only ?P to Delaware
```

### 4.3 Distribute Event

Models a stock distribution (pro-rata or N-for-one):

```lisp
(Distribute <subject> <object> <owner> <recipients> <time>)
; "subject distributes object (owned by owner) to recipient class at time"
```

**Expansion logic (pseudocode):**

```
function expand_distribute(subject, object, owner, recipient_class, time):
    for each R matching recipient_class in DB:
        P = new_symbol()
        assert NSHARES(P, compute_shares(R, distribution_rule))
        assert SPLITPIECE(P, object, time)  [expand]
        assert TRANS(subject, P, owner, R, time)  [expand]
```

**Distribution rule formats:**

```lisp
(Distribution-Rule <distribution> (N for one))    ; N shares per 1 held
(Distribution-Rule <distribution> (Prorata))      ; proportional
```

**Example — NJ distributes Delaware common stock 2-for-1 to NJ common holders:**

```lisp
(Distribute NEW-JERSEY PHE26 NEW-JERSEY
            <common-stockholders-of-NJ>
            <time>)
; recipient class = (Find All (STOCKHOLDER ?R NEW-JERSEY) Abstract)
;                   filtered by (COMMON <their stock>)
; each gets 2 shares of Delaware per 1 NJ share held
```

### 4.4 Full Case Representation

```
1. Write initial state description (Assert all base facts)
2. Write event descriptions in chronological order
3. Expand events in order → produces sequence of modified state descriptions
4. DB now contains all states T0, T1, T2, ... Tn with time-indexed propositions
```

---

## 5. Analysis Mechanisms (Goal-Based)

### 5.1 Control

Statutory definition: ≥ 80% of voting stock AND ≥ 80% of all other share classes.

```lisp
(THEOREM ABSTRACT (X Y T)
  (CONTROL ?X ?Y ?T)

  ; Step 1: does X own any stock of Y at all?
  (Goal (STOCKHOLDER ?X ?Y ?T) Abstract)

  ; Step 2: locate all stock classes issued by Y
  (Find All S where (ISSUE ?Y ?S ?T) AND (STOCK ?S ?T)):

  ; Step 3: partition into voting and non-voting
  for each S:
    if (GOAL (VOTING ?S ?T)):
      add to voting_stocks
    else:
      add to nonvoting_stocks

  ; Step 4: for each stock S in each class, compute X's ownership
  for each S in voting_stocks:
    find all P where (PIECE-OF ?P S ?T) AND (OWN ?X ?P ?T)
    total_x_votes += sum(NSHARES(P))
    find all P where (PIECE-OF ?P S ?T)
    total_votes    += sum(NSHARES(P))

  ; Step 5: same for nonvoting share count
  ; Step 6: verify both ratios ≥ 0.80
  assert (CONTROL X Y T) if both tests pass)
```

### 5.2 B-Reorganization

**Statute:** Acquisition by one corp, solely for voting stock, of stock of another corp,
such that immediately after, the acquirer controls the acquired.

```lisp
(THEOREM ABSTRACT (A C T)
  (B-REORGANIZATION ?A ?C ?T)

  ; Search order (efficiency heuristic):
  ; 1. Find earliest Control relationship
  (Goal (CONTROL ?A ?C ?T_ctrl) Abstract)   ; T_ctrl = time control achieved

  ; 2. Search backwards for stock transfers TO A before T_ctrl
  find all Trans where recipient=A and time ≤ T_ctrl

  ; 3. Build Acquisition structure:
  (ACQUISITION
    (list (EXCHANGE
            (list (TRANS ?S1 ?X1 ?O1 A <time>) ...)     ; A receives stock
            (list (TRANS A ?X2 A ?O1 <time>) ...))))     ; A gives voting stock

  ; 4. Apply constraints:
  ; - R1 (acquirer) must be a Corporation
  ; - Each X1 transferred TO A must be a Piece-of a Stock Issued by C
  ; - Each X2 transferred FROM A must be Piece-of a Voting Stock Issued by A
  ;   (or by a corp that A controls)
  ; - Control must hold immediately after the final acquisition
)
```

**Acquisition data structure:**

```lisp
(ACQUISITION
  (list (EXCHANGE
          (list (TRANS S1 X1 O1 R1 <time>) ...)    ; side 1: what R1 receives
          (list (TRANS S2 X2 O2 R2 <time>) ...))   ; side 2: what R2 receives
        (EXCHANGE ...)))                            ; additional exchanges if any
; R1 = acquirer (recipient in first Trans list)
; R2 = acquired party
; "solely for voting stock" → all X2's must be Voting Stock pieces
```

### 5.3 C-Reorganization

**Statute:** Acquisition of substantially all properties of another corp, solely for voting stock.

```lisp
(THEOREM ABSTRACT (A C T)
  (C-REORGANIZATION ?A ?C ?T)

  ; Same Acquisition structure as B
  ; Additional constraint: X transferred FROM C must be
  ;   "substantially all properties" of C
  ;   (check: does C retain significant assets after transfer?)

  ; "Solely for voting stock" constraint applies to what C receives
)
```

### 5.4 D-Reorganization

**Statute:** Transfer of assets by corp to another corp which the transferor (or shareholders) control immediately after.

```lisp
(THEOREM ABSTRACT (A C T)
  (D-REORGANIZATION ?A ?C ?T)

  ; Structural core:
  (TRANS NEW-JERSEY ?X NEW-JERSEY DELAWARE ?T)   ; asset transfer
  (CONTROL NEW-JERSEY DELAWARE ?T)               ; transferor controls transferee after

  ; Note: full D-Reorg also requires qualifying distribution under §354/355/356
  ; Current TAXMAN cannot implement distribution check — partial implementation only
)
```

### 5.5 Phellis Case Query Example

```lisp
; Query 1: Is there a B-Reorganization with A=Delaware, C=NJ?
(Goal (B-Reorganization Delaware New-Jersey ?T) Abstract)
; FAILS — Delaware never acquires NJ stock
; Failure point: (Goal (CONTROL Delaware New-Jersey ?T)) → no match

; Query 2: Is there a B-Reorganization with A=NJ, C=Delaware?
(Goal (B-Reorganization New-Jersey Delaware ?T) Abstract)
; PARTIAL MATCH — finds Acquisition:
; (EXCHANGE
;   ((TRANS DELAWARE PHE29 DELAWARE NEW-JERSEY PHE30)
;    (TRANS DELAWARE PHE31 DELAWARE NEW-JERSEY PHE32))
;   ((TRANS NEW-JERSEY PHE26 NEW-JERSEY DELAWARE PHE28)))
; FAILS "solely for voting stock" — PHE26 = NJ assets, not stock
; → B-Reorg fails correctly

; Query 3: C-Reorganization
(Goal (C-Reorganization ?A ?C ?T) Abstract)
; Finds: A=Delaware, C=New-Jersey, exchange=PHE28 (NJ's assets → Delaware)
; System checks: is PHE26 "substantially all properties"? YES
; Checks: voting stock exchanged? PHE29=debenture, PHE31=common (stipulated voting)
; → Returns: (C-Reorganization Delaware New-Jersey PHE28)

; Query 4: D-Reorganization (partial)
(Goal (D-Reorganization ?A ?C ?T) Abstract)
; Finds:
;   ((TRANS NEW-JERSEY PHE26 NEW-JERSEY DELAWARE PHE28))  ; asset transfer
;   ((CONTROL NEW-JERSEY DELAWARE PHE32)
;    (CONTROL NEW-JERSEY DELAWARE PHE33)
;    (CONTROL NEW-JERSEY DELAWARE PHE36))
; → Returns: (D-Reorganization New-Jersey Delaware PHE28)
```

---

## 6. Abstraction Hierarchy

```
HIGH LEVEL (legal conclusions)
    B-Reorganization
    C-Reorganization
    D-Reorganization
         │ defined via Abstract theorems over ↓
    Control
    Acquisition
    Distribute (analysis mode)
         │ defined via Abstract theorems over ↓
    Stockholder
    Voting
         │ defined via Abstract theorems over ↓
    Issue, Stock, Piece-of, Own, Nshares  ← base network propositions
LOW LEVEL (raw facts)

EXPANSION DIRECTION (Expand theorems run top → down)
ABSTRACTION DIRECTION (Abstract theorems run bottom → up)
```

Multiple hierarchies can extend from the same base network in different directions.
"Primitive" concepts are primitive only provisionally and for specific purposes.

---

## 7. Key Implementation Patterns

### 7.1 Pattern Matching in Goal

Partial specification in a Goal matches the DB with variable slots:

```lisp
(GOAL (ISSUE ?C ?S ?T))
; matches any (ISSUE x y z) triple, binds C, S, T
```

Nested patterns (via Prog/Theorem) match subgraph structures.

### 7.2 If-Then inside Theorem bodies

```lisp
(IF (GOAL (OWN ?O ?X ?T0))
  THEN
    (ERASE  (OWN ?O ?X ?T))
    (ASSERT (OWN ?R ?X ?T)))
```

Used in Trans expansion to conditionally update state.

### 7.3 GEN — Fresh Symbol Generation

```lisp
(PROG (P = (GEN))   ; P ← fresh unique symbol, e.g. PHE42
  ...)
```

Used whenever nominalization requires a new object in the network.

### 7.4 Search Order as Legal Policy

The order in which Acquisition vs. Control is located determines answers to
"creeping acquisition" questions:

```
If Control located first → then scan back for prior Acquisitions
  → tends to treat a series of purchases as one reorganization

If Acquisition structure built first → then check Control at end
  → tends to require control achieved in a single transaction
```

Current TAXMAN locates Control first, then searches backward for Acquisitions.
This is an implementation decision with substantive legal implications.

### 7.5 Multiple and Partial Matches

TAXMAN automatically surfaces **partial matches** and **multiple matches**:

- The same set of Trans propositions appears in both the C-Reorg and the
  partial B-Reorg pattern for Phellis, with argument order reversed.
- The same Control structure appears in both B-Reorg (paired with stock acquisition)
  and D-Reorg (paired with asset transfer).
- These overlaps model the real statutory overlap between reorganization types.

---

## 8. Phellis Case Data (Simplified)

### Initial State (T0 = pre-Oct 1, 1915)

```lisp
(CORPORATION NEW-JERSEY)
(ISSUE NEW-JERSEY PHE1 )  (STOCK PHE1)  (PREFERRED PHE1)   ; NJ preferred
(ISSUE NEW-JERSEY PHE2 )  (STOCK PHE2)  (COMMON PHE2)      ; NJ common
(ISSUE NEW-JERSEY PHE3 )  (BOND PHE3)   ; 5% mortgage bonds
(ISSUE NEW-JERSEY PHE4 )  (BOND PHE4)   ; 4.5% 30-yr bonds
; Phellis owns 250 shares of NJ common:
(PIECE-OF PHE5 PHE2)   (NSHARES PHE5 250)   (OWN PHELLIS PHE5)
```

### Key Events (in order)

```lisp
; 1. NJ transfers all assets to new Delaware corp
(Trans NEW-JERSEY PHE26 NEW-JERSEY DELAWARE <T1>)
; PHE26 = NJ's operating assets (valued $120M)

; 2. Delaware issues debenture stock to NJ
(Trans DELAWARE PHE29 DELAWARE NEW-JERSEY <T1>)
; PHE29 = 6% cumulative debenture stock

; 3. Delaware issues common stock to NJ
(Trans DELAWARE PHE31 DELAWARE NEW-JERSEY <T1>)
; PHE31 = Delaware common stock ($58,854,200 par value)

; 4. NJ distributes Delaware common to NJ common stockholders (2-for-1)
(Distribute NEW-JERSEY PHE31 NEW-JERSEY <NJ-common-holders> <T2>)
; Phellis receives PHE28 = 500 shares of Delaware common @ $347.50/share

; 5. NJ redeems 5% bonds with cash
; 6. NJ exchanges debenture stock for preferred + 30-yr bonds
```

### Expanded DB symbols (prefix PHE)

The full expanded network contains ~50 internally generated symbols.
Each represents a stock class, bond class, or ownership interest created during
the transaction sequence.

---

## 9. Limitations of Current System

| Capability | Status |
|---|---|
| Classify B, C, D reorganizations | ✓ Implemented |
| Continuity-of-interest doctrine | ✗ Not implemented |
| Business purpose doctrine | ✗ Not implemented |
| Step transaction doctrine | ✗ Not implemented |
| Nonrecognition rules (§354/361) | ✗ Not implemented |
| Basis rules (§358/362) | ✗ Not implemented |
| Distribution rules (§354/355) | ✗ Not implemented |
| "Substantially all properties" test | ✗ Partial only |
| Creeping acquisitions (time-bounded) | ✗ Incorrect |
| Natural language I/O | ✗ Not implemented |
| Internal corporate decisions | ✗ Not representable |
| Corporate "business" / "purpose" | ✗ Not representable |

---

## 10. Feasible Extensions (Roadmap)

1. **Nonrecognition rules** — model §354 as an Exchange abstraction theorem;
   §358 basis rules follow from gain-recognition arithmetic on the same network.

2. **Better temporal model** — replace linear time list with partial order of
   time-points connected by "before"/"after"/"overlaps" relations; allows
   incomplete and inconsistent temporal knowledge.

3. **Flexible description order** — accept case facts in any order; system builds
   temporal model and expands as needed, rather than requiring strict sequence.

4. **Planning mode** — given initial state + desired legal conclusion, search for
   a transaction sequence that achieves it. Analogous to organic synthesis planners.
   Can reproduce the Elkhorn Coal manipulation (Type D → C → B sequence).

5. **Natural language front-end** — micro-Planner is designed to plug into
   Winograd-style NL systems; feasible once core conceptual structures are stable.

6. **Stock/security expansion** — expand the primitive `Stock` concept into a
   hierarchy of voting rights, dividend provisions, liquidation priorities, etc.
   Enables representation of hybrid securities.

---

## 11. Programming Language Notes

- Written in **micro-Planner** (a subset of Planner), itself implemented in **Lisp**.
- Some portions written directly in Lisp.
- Core Planner constructs used: `Assert`, `Erase`, `Goal`, `Prog`, `Theorem`
  (labeled `Abstract` or `Expand` to distinguish direction).
- Backtracking is automatic in Prog/Goal but **not programmer-controllable** —
  this is the primary criticized limitation of micro-Planner vs. Conniver.
- Truth = presence in DB. Falsity/unknown = absence (two-valued, not three-valued).
  Conniver alternative: explicit true/false/indeterminate markers.
- Pattern matching = core operation: match a partially-specified list against
  fully-specified DB entries, binding unassigned variables.