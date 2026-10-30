# Project architecture

This diagram shows the **target architecture** of the native Windows connector.
It is a visual guide to the [project specification](PROJECT_SPECIFICATION.md),
which owns the requirements and boundaries. Source ownership packages and Phase 0
experiments exist; the production UI, adapters and sync engine are still planned.
See [current progress](STATE_AND_PROGRESS.md) for implemented capabilities.

## System overview

```mermaid
flowchart TB
    subgraph cloud["INNOFORAI BAHI / BILLING - Cloud ERP"]
        api["Existing REST APIs<br/>Business, parties, groups, items, invoices"]
        proposed["Proposed sync capabilities - not deployed<br/>Change feed, outcome lookup, versions, ack, writer lease"]
    end

    subgraph windows["CLIENT WINDOWS MACHINE"]
        subgraph connector["INNOFORAI TALLY CONNECTOR - Native Windows .exe"]
            subgraph main["MAIN THREAD - PySide6"]
                gui["Desktop GUI and system tray<br/>Status, Sync Now, settings, activity, failures/conflicts"]
                bridge["UI bridge and controllers"]
                gui -->|Commands| bridge
                bridge -->|Queued Qt events| gui
            end

            dispatch["Application services and background dispatch<br/>Coalesce manual and timer triggers<br/>Cloud poll: 60s / Tally capture: 120s defaults"]
            bridge -->|Dispatch work| dispatch

            subgraph storage["LOCAL SQLITE - WAL / bounded transactions"]
                metadata[("sync_metadata.db<br/>Bindings, mappings, operations, attempts,<br/>outbox, checkpoints, versions, content hashes")]
                queue[("huey_queue.db<br/>Huey-owned persistent execution queue")]
            end

            dispatch -->|Commit captured operations and outbox| metadata
            metadata -->|Recover pending outbox entries| dispatch
            dispatch -->|Enqueue durable operation IDs| queue
            queue --> worker["Embedded SqliteHuey<br/>One background thread worker<br/>Bounded tasks and graceful shutdown"]

            subgraph core["APPLICATION + DOMAIN - Framework-independent rules and ports"]
                features["Feature use cases<br/>Purchases, sales, masters"]
                sync["Shared sync execution<br/>Validate mappings, save intent, apply, read back<br/>Reconcile unknown outcomes and resolve conflicts"]
                features --> sync
            end

            worker -->|Execute application commands| features
            sync <-->|Short transactions through persistence ports| metadata
            sync -->|Status and result events| bridge

            bahi["Bahi adapter<br/>REST schemas / reused HTTPX connections<br/>Separate invoice DRAFT and POST operations"]
            tallyGateway["One shared Tally gateway<br/>Serialized background access for ALL requests<br/>Company checks, exports, imports, read-back"]
            sync -->|Through Bahi port| bahi
            sync -->|Through Tally port| tallyGateway

            host["Windows host services<br/>Credential Manager, instance lock, runtime paths"]
            diagnostics["Diagnostics<br/>Bounded, rotating, redacted logs"]
        end

        tally["TALLYPRIME<br/>Explicitly bound company identity"]
        tallyGateway <-->|HTTP POST / XML - localhost:9000 default| tally
    end

    bahi <-->|Outbound HTTPS requests and responses / Keep-Alive| api

    classDef cloudStyle fill:#e8f1ff,stroke:#3268a8,color:#162e49;
    classDef storageStyle fill:#fff5d6,stroke:#a57919,color:#49380d;
    classDef coreStyle fill:#e7f5ed,stroke:#33865a,color:#163e29;
    classDef proposedStyle fill:#fff1e6,stroke:#b56628,stroke-dasharray:5 5,color:#643510;
    class api cloudStyle;
    class proposed proposedStyle;
    class metadata,queue storageStyle;
    class features,sync coreStyle;
```

The cloud connection above terminates at the Bahi adapter. Both adapters return
results through application ports; they do not call each other. The diagram
groups responsibilities rather than specifying exactly two operating-system
threads: Huey includes consumer/scheduler lifecycle work as well as its single
task worker. Use the [tested Qt/Huey embedding recipe](phase0/QT_HUEY_COMPATIBILITY.md).

## How synchronization moves through the system

1. A timer or Sync Now dispatches background work through the UI bridge and
   services. Repeated triggers are coalesced; the GUI stays responsive.
2. Capture reads the selected source through its adapter. It commits operations,
   outbox entries and the capture checkpoint together in the metadata database.
   Dispatch then queues operation IDs; startup recovery repairs missed dispatches.
3. The worker executes the relevant use case, validates the business/company
   binding and confirmed mappings, and records write intent before external IO.
4. The destination adapter applies the change. Every Tally request, including
   health and company checks, uses the same serialized gateway. HTTP calls run
   outside database transactions.
5. Identity and supported canonical content are read back before completion.
   Unknown outcomes enter reconciliation before any retry. A failed backend
   acknowledgment retries the acknowledgment without recreating the voucher.
6. Persisted results produce queued UI events for status, activity and failures.

This flow applies in both directions. Tally-to-Bahi invoice DRAFT creation and
accounting posting remain separate operations. Safe retries use a bounded policy;
authentication, missing mappings and conflicts require action.

## Storage, scheduling and backend boundaries

- Runtime data lives under `%LOCALAPPDATA%\InnoforaiTallySync\`. API secrets live
  in Windows Credential Manager; local configuration stores credential references.
  Credentials and raw business payloads are not Huey task arguments.
- The two databases have separate owners. Metadata transactions cannot atomically
  commit Huey queue changes, which is why durable outbox recovery is required.
- Polling runs only in supported modes. A 30-second option needs a separately
  tested trigger because Huey's periodic checks are minute-based.
- The supplied `/v1/sync/pending`, `/v1/sync/ack` and `/v1/sync/from-tally` routes
  are illustrative proposals, not verified deployed endpoints. The
  [backend handoff](api/bahi/SYNC_EXTENSION_CONTRACT.md) owns the proposed contracts.
- Automatic bidirectional mutation depends on verified change capture,
  idempotency/outcome lookup, version handling, origin/ack and writer ownership.
  Local serialization alone does not prevent another PC from writing.
- The connector initiates cloud requests and uses Tally's HTTP interface. It
  runs as a native desktop/tray application without a local web server.

For package-level ownership, see the
[layout and dependency rules](PROJECT_SPECIFICATION.md#dependency-and-ownership-rules).
For delivery gates, see the [implementation plan](IMPLEMENTATION_PLAN.md).
