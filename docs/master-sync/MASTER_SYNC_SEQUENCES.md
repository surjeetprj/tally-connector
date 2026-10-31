# Master sync sequence diagrams

Status: **PLANNED BEHAVIOR**, not executed master-sync code. Read each diagram
from top to bottom: a horizontal arrow is a message, and later messages appear
lower down. Component names are bold uppercase. These are logical interactions,
not proposed Python method signatures or additional threads.

## 1. Link two existing masters

**Example:** the user confirms that a Bahi supplier and a Tally supplier ledger
represent the same business. Linking saves a relationship locally; it does not
change either remote record.

<!-- diagram-start: master-link-existing -->
<p><a href="../diagrams/master-link-existing.svg"><img src="../diagrams/master-link-existing.svg" alt="Link existing masters" width="858" style="width: 858px; max-width: 100%; height: auto;"></a></p>

<details>
<summary>Editable Mermaid source</summary>

<!-- diagram: master-link-existing -->
```mermaid
sequenceDiagram
    accTitle: Link existing masters
    accDescr: The user confirms a pair of existing master records, which are rechecked and linked locally without remote modification.
    participant UI as USER SCREEN
    participant APP as BACKGROUND SERVICES
    participant DATA as LOCAL STORAGE
    participant ADAPTERS as BAHI AND TALLY CONNECTIONS

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

[Source file](../diagrams/sources/master-link-existing.mmd)

</details>
<!-- diagram-end: master-link-existing -->

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

<!-- diagram-start: master-transfer -->
<p><a href="../diagrams/master-transfer.svg"><img src="../diagrams/master-transfer.svg" alt="Successful master transfer" width="1073" style="width: 1073px; max-width: 100%; height: auto;"></a></p>

<details>
<summary>Editable Mermaid source</summary>

<!-- diagram: master-transfer -->
```mermaid
sequenceDiagram
    accTitle: Successful master transfer
    accDescr: Save durable intent and the write attempt, send the approved master, read back the target and record verified completion.
    participant UI as USER SCREEN
    participant APP as BACKGROUND SERVICES
    participant DATA as LOCAL STORAGE
    participant WORK as WORKER AND SYNC ENGINE
    participant TARGET as DESTINATION CONNECTION

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

[Source file](../diagrams/sources/master-transfer.mmd)

</details>
<!-- diagram-end: master-transfer -->

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

<!-- diagram-start: master-recovery -->
<p><a href="../diagrams/master-recovery.svg"><img src="../diagrams/master-recovery.svg" alt="Uncertain master write recovery" width="855" style="width: 855px; max-width: 100%; height: auto;"></a></p>

<details>
<summary>Editable Mermaid source</summary>

<!-- diagram: master-recovery -->
```mermaid
sequenceDiagram
    accTitle: Uncertain master write recovery
    accDescr: Investigate a possibly applied create; record verified recovery or keep uncertainty visible without automatically creating again.
    participant WORK as WORKER AND SYNC ENGINE
    participant DATA as LOCAL STORAGE
    participant TARGET as DESTINATION CONNECTION
    participant UI as USER SCREEN

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

[Source file](../diagrams/sources/master-recovery.mmd)

</details>
<!-- diagram-end: master-recovery -->

An absent name-search result is not proof that the first create failed. When
available evidence proves a different result, show the mismatch/conflict rather
than claiming recovery succeeded. Bahi party creation currently lacks verified
idempotency/outcome lookup; the diagram does not introduce a new deployed API.
Known returned IDs permit targeted reads, but an unknown result may remain
unresolved. Retrying a create requires authoritative evidence that replay is safe.

See [operation states](MASTER_SYNC_STATES.md),
[design](MASTER_SYNC_DESIGN.md) and
[failure experiments](MASTER_SYNC_VALIDATION.md#failure-and-recovery-matrix).
