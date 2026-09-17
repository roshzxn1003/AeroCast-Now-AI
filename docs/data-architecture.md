# AeroCast-Now AI: Operational Data Architecture (Phase 9)

## 1. System Overview & Philosophy
AeroCast-Now AI operational data infrastructure follows the meteorological lifecycle:
$$\text{Observe} \longrightarrow \text{Validate} \longrightarrow \text{Store} \longrightarrow \text{Synchronize} \longrightarrow \text{Predict} \longrightarrow \text{Record} \longrightarrow \text{Verify} \longrightarrow \text{Learn} \longrightarrow \text{Improve}$$

The architecture guarantees:
- **Zero Silent Fabrication**: No artificial weather figures are injected into real operational forecasts. Missing data is explicitly isolated from genuine zero readings.
- **Provider Redundancy**: Every atmospheric domain maintains a Primary and Secondary data provider with automated circuit-breaker failover and recovery.
- **Strict Data Segregation**: Operational modes (`REAL`, `REPLAY`, `TEST`, `SIMULATION`) are isolated with cryptographic SHA-256 provenance tags.
- **Immutable Raw Artifact Preservation**: All incoming payloads are preserved in partition directories before normalization or model inference.

---

## 2. Ingestion Layers

```mermaid
flowchart TD
    subgraph External Sources
        R1[IMD DWR Network]
        R2[RainViewer Mosaic]
        S1[ISRO/IMD INSAT-3D]
        S2[Open-Meteo Cloud]
        L1[Blitzortung TOA Live]
        L2[Lightning Archive]
        N1[Open-Meteo NWP]
        N2[Tropical Climatology]
    end

    subgraph Adapters & Circuit Breakers
        A_R[Radar Adapters + Circuit]
        A_S[Satellite Adapters + Circuit]
        A_L[Lightning Adapters + Circuit]
        A_N[NWP Adapters + Circuit]
    end

    R1 & R2 --> A_R
    S1 & S2 --> A_S
    L1 & L2 --> A_L
    N1 & N2 --> A_N

    subgraph Operational Provider Manager
        PM[ProviderManager Engine\nPrimary -> Secondary Failover\nFallback Ledger & Telemetry]
    end

    A_R & A_S & A_L & A_N --> PM

    subgraph Storage & Audit
        RAW[(data/raw/<domain>/YYYY/MM/DD/\nSHA-256 Deduplication)]
        DB[(SQLite WAL Store\nraw_ingestion_log\nprovider_status\nfallback_events\nobservations)]
    end

    PM --> RAW
    PM --> DB

    subgraph Harmonization & Gating
        TS[Temporal Synchronizer\nSnap to T-45, T-30, T-15, T0\nBounded Forward-Fill <= 30m]
        RG[Geospatial Regridder\nWGS84 EPSG:4326\n32x32 @ 4km Domain Mesh]
        QC[Atmospheric Quality Control\nPhysical Bounds & Consistency]
        GATE[Inference Readiness Gate\nREADY / DEGRADED / BLOCKED]
    end

    PM --> TS --> RG --> QC --> GATE

    subgraph Model Boundary
        GATE -->|Tensor (1, 4, 32, 32, 4)| MM[ModelManager ConvLSTM]
    end
```

---

## 3. Storage Hierarchy & Layout
- **Raw Payloads**: `data/raw/<domain>/<YYYY>/<MM>/<DD>/<provider_id>_<HHMMSS>_<hash[:8]>.<ext>`
- **Relational Store**: SQLite with Write-Ahead Logging (`WAL`), `synchronous = NORMAL`, `foreign_keys = ON` in `data/aerocast.sqlite3`.
  - `observations`: Canonical observation records with quality flags and JSON payloads.
  - `raw_ingestion_log`: Cryptographic deduplication index and ingestion status (`STORED`, `DUPLICATE`, `FAILED`).
  - `provider_status`: Real-time circuit breaker health, failure counts, and latency tracking.
  - `fallback_events`: Redundancy audit trail recording failover reasons and timestamps.
  - `data_quality_log`: Real-time logging of physical limit violations and sensor cross-check anomalies.
