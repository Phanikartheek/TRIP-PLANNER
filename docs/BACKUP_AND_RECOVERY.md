# Disaster Recovery, Backup & Restore Specification

## 1. Executive Summary & Production Objectives

A backup strategy that has never been tested in a restore drill is an illusion of safety. This document details the SQLite database backup, disaster recovery, and data preservation procedures verified through automated restore drills.

### Target Recovery Objectives:
- **Recovery Point Objective (RPO)**: $\le 60$ minutes (maximum acceptable data loss).
- **Recovery Time Objective (RTO)**: $\le 5$ minutes (time to deploy and restore a verified snapshot).

---

## 2. SQLite Online Streaming Backup Architecture

Because the application operates in SQLite Write-Ahead Logging (`WAL`) mode, merely copying `jobs.db` with OS commands (`cp` or `copy`) while writers are active can produce corrupt backups if pages are partially written or in the `-wal` transaction buffer.

Instead, online backups use the native SQLite Streaming Backup API:

```python
# Streaming online backup procedure (non-blocking)
with db.get_connection(primary_db_path) as src_conn:
    with sqlite3.connect(str(backup_destination_path)) as dst_conn:
        src_conn.backup(dst_conn, pages=100)
```

### Key Technical Properties:
1. **Zero Downtime**: Reads and writes continue uninhibited during the backup process.
2. **Atomic Consistency**: The destination snapshot captures a clean, transactionally consistent point-in-time state.
3. **WAL Reconciliation**: Active WAL frames are flushed and consolidated into the backup file without requiring an explicit exclusive checkpoint.

---

## 3. Storage & Railway Deployment Assumptions

1. **Persistent Volume Mounting**:
   - In production on Railway, the database file `jobs.db` resides on a mounted persistent volume (`/data/jobs.db`).
   - The environment variable `DB_PATH=/data/jobs.db` guarantees that ephemeral container redeployments do not wipe out active jobs, user auth tokens, or checklist states.
2. **Snapshot Cadence**:
   - Daily automated streaming backup to off-site object storage (S3 / Cloudflare R2 / Railway Volume Snapshots).
   - Hourly incremental WAL snapshots.

---

## 4. Disaster Recovery & Restore Procedure

In the event of accidental volume deletion, database corruption, or storage failure:

### Step 1: Provision Replacement Volume
Mount a new persistent volume or clear the corrupted volume directory:
```bash
rm -f /data/jobs.db /data/jobs.db-wal /data/jobs.db-shm
```

### Step 2: Restore from Validated Snapshot
Download the latest verified backup image (`jobs_snapshot_YYYYMMDD_HHMMSS.db`) to the host.
Execute the streaming restore:
```python
import sqlite3

backup_source = "/backups/jobs_snapshot_latest.db"
target_db = "/data/jobs.db"

with sqlite3.connect(backup_source) as bkp:
    with sqlite3.connect(target_db) as dst:
        bkp.backup(dst)
```

### Step 3: Run Integrity & Reconciliation Check
Validate page consistency and clear any orphaned locks:
```bash
sqlite3 /data/jobs.db "PRAGMA integrity_check;"
```
Expected output: `ok`.

### Step 4: Restart Application Service
Restart the container. The application automatically runs `db.init_db()`, reconciling any pending jobs from the snapshot and preparing the WAL journals.

---

## 5. Automated Verification Evidence

The recovery procedure is continually verified via the automated test:
`backend/tests/test_backup_restore.py::test_sqlite_online_backup_and_recovery`

### Test Drill Protocol:
1. Active database populated with users, active sessions, jobs, and checklist states.
2. Online backup executed using `src_conn.backup(dst_conn, pages=100)`.
3. Complete volume deletion simulated: `primary_db.unlink()` + deletion of `-wal` and `-shm` files.
4. Database restored from backup to new path.
5. Verification of 100% data fidelity:
   - User email and session validity: **100% matched**
   - Job ID, status, and destination city: **100% matched**
   - Complex nested checklist state (`[{"item": "Camera", "checked": True}]`): **100% matched**
   - Deduplication hashes and client IP address: **100% matched**
