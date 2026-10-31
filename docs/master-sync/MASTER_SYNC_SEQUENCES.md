# Master sync sequence diagrams

Status: **PLANNED BEHAVIOR**, not executed master-sync code. Read each diagram
from top to bottom: a horizontal arrow is a message, and later messages appear
lower down. Component names are bold uppercase. These are logical interactions,
not proposed Python method signatures or additional threads.

## 1. Link two existing masters

**Example:** the user confirms that a Bahi supplier and a Tally supplier ledger
represent the same business. Linking saves a relationship locally; it does not
change either remote record.

```mermaid
sequenceDiagram
    participant UI as <b>USER SCREEN</b>
    participant APP as <b>BACKGROUND SERVICES</b>
    participant DATA as <b>LOCAL STORAGE</b>
    participant ADAPTERS as <b>BAHI AND TALLY CONNECTIONS</b>

    UI->>APP: Load masters for the confirmed business and company
    APP->>ADAPTERS: Read supported records and their identities
    ADAPTERS-->>APP: Records and read coverage
    APP-->>UI: Suggested matches and differences
    UI->>APP: Confirm one pair as LINK EXISTING
    APP->>ADAPTERS: Recheck identities and classification
    ADAPTERS-->>APP: Current observations
    APP->>DATA: Save unique mapping and each side's baseline
    DATA-->>APP: Mapping saved
    APP-->>UI: Linked locally with no remote fields changed
```

The combined connection participant keeps the picture short. Actual Bahi and
Tally adapters are separate; all Tally reads use the shared serialized gateway.
Differences between linked records stay visible. Linking does not mark unequal
content as equal or authorize a later overwrite. Ambiguous matches require a
user decision, as specified in [matching rules](MASTER_MATCHING_RULES.md).

## 2. Transfer one master successfully

**Example:** create an approved customer in the selected destination. The
**DESTINATION CONNECTION** means Bahi's adapter for Tally-to-Bahi transfers, or
the shared Tally gateway for Bahi-to-Tally transfers. Source records have already
been loaded for preview; execution rechecks their freshness and dependencies.

```mermaid
sequenceDiagram
    participant UI as <b>USER SCREEN</b>
    participant APP as <b>BACKGROUND SERVICES</b>
    participant DATA as <b>LOCAL STORAGE</b>
    participant WORK as <b>WORKER AND SYNC ENGINE</b>
    participant TARGET as <b>DESTINATION CONNECTION</b>

    UI->>APP: Confirm the displayed transfer and direction
    APP->>DATA: Commit operation and pending dispatch together
    DATA-->>APP: Saved durable operation ID
    APP->>WORK: Queue the operation ID through Huey
    WORK->>DATA: Load intent, binding and confirmed mappings
    WORK->>WORK: Recheck source, destination and dependencies through ports
    Note over WORK: Stop here if the preview is stale or validation fails
    WORK->>DATA: Save the write attempt before sending
    DATA-->>WORK: Attempt saved
    WORK->>TARGET: Create the approved master
    TARGET-->>WORK: Response with identity or lookup evidence
    WORK->>DATA: Save returned identity immediately when available
    WORK->>TARGET: Read back the exact target record
    TARGET-->>WORK: Identity and supported business fields
    WORK->>WORK: Compare actual result with intended content
    WORK->>DATA: Save verified mapping, baseline and completion
    WORK-->>UI: Queued event: transfer verified
```

**The important order is SAVE → SEND → READ BACK → VERIFY.** A response or import
counter alone is insufficient. Missing identity or mismatched content follows
investigation/conflict handling rather than the success path shown here.

The UI confirmation reaches background services through its bridge/controllers;
the screen does not access Huey directly. The worker uses application ports,
not concrete adapter imports. Metadata and Huey's queue are separate databases:
pending dispatch is recorded with the operation, then queued separately. Startup
recovery can redispatch a missed operation ID without creating another intent.
Database transactions end before HTTP. The source and destination may still be
edited concurrently; preflight reads do not replace conditional-write contracts.

For an allowed update, the same sequence uses the already mapped target identity
and only approved fields. The expected-version/content checks must still pass.
There is no invoice creation, posting or stock-balance write in this workflow.

## 3. A request may have succeeded, but the response is lost

**Example:** the connection times out after sending a master create. The
destination may already contain the master. The connector must investigate
before sending another create request.

```mermaid
sequenceDiagram
    participant WORK as <b>WORKER AND SYNC ENGINE</b>
    participant DATA as <b>LOCAL STORAGE</b>
    participant TARGET as <b>DESTINATION CONNECTION</b>
    participant UI as <b>USER SCREEN</b>

    WORK->>DATA: Save intent and attempt before sending
    WORK->>TARGET: Send master create
    Note over WORK,TARGET: Response is lost or the process stops after send
    WORK->>DATA: On timeout or restart, retain uncertain outcome
    WORK-->>UI: Needs investigation - do not create again
    WORK->>TARGET: Read-only identity or authoritative outcome lookup, if available
    alt Exact result is established and content matches
        TARGET-->>WORK: Verified target identity and content
        WORK->>DATA: Save recovered mapping and verified completion
        WORK-->>UI: Recovered successfully
    else Result cannot be established
        TARGET-->>WORK: Unsupported lookup, ambiguity or insufficient evidence
        WORK->>DATA: Retain unresolved intent and diagnostic evidence
        WORK-->>UI: Still unresolved - automatic create retry blocked
    end
```

An absent name-search result is not proof that the first create failed. When
available evidence proves a different result, show the mismatch/conflict rather
than claiming recovery succeeded. Bahi party creation currently lacks verified
idempotency/outcome lookup; the diagram does not introduce a new deployed API.
Known returned IDs permit targeted reads, but an unknown result may remain
unresolved. Retrying a create requires authoritative evidence that replay is safe.

See [operation states](MASTER_SYNC_STATES.md),
[design](MASTER_SYNC_DESIGN.md) and
[failure experiments](MASTER_SYNC_VALIDATION.md#failure-and-recovery-matrix).
