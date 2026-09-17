# Historical Replay Engine & Case Study Backtesting (Phase 9)

## 1. Purpose & Architecture
The `HistoricalReplayEngine` allows meteorologists, disaster management planners, and researchers to replay historical weather events through the exact operational nowcasting pipeline.

### Core Principles
- **Strict Mode Segregation**: During replay, the system mode is set to `REPLAY`. All forecasts and outputs are marked with `is_replay=True` and provenance `REPLAY_ARCHIVE`.
- **Zero Real Data Contamination**: Replay executions never overwrite operational live logs or trigger real-world emergency broadcasts.
- **Variable Time Stepping**: Supports step-by-step playback or real-time simulation multipliers ($1\times, 10\times, 100\times$).

---

## 2. Replay API Contract

### Start Replay Session
`POST /data/replay`
```json
{
  "action": "start",
  "start_time": "2026-09-15T12:00:00Z",
  "end_time": "2026-09-15T15:00:00Z",
  "speed_multiplier": 10.0,
  "step_minutes": 15
}
```

### Advance Replay Step
`POST /data/replay`
```json
{
  "action": "step"
}
```

### Check Replay Status
`GET /data/replay`
```json
{
  "is_active": true,
  "session_id": "REPLAY-20260916084500",
  "current_time": "2026-09-15T12:45:00+00:00",
  "progress_pct": 25.0
}
```

### Stop Replay Session
`POST /data/replay`
```json
{
  "action": "stop"
}
```
Reverts operational mode cleanly back to `REAL`.
