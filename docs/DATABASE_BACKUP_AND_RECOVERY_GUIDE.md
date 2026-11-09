# Database Backup and Recovery Guide

## 1. Project Information

- Project: AI Personalized Learning Planner
- Database: ai_learning_planner
- Database Engine: MySQL 8.0
- Python Database Driver: mysql+pymysql
- Backup Utility: mysqldump
- Backup Manager: app/database/backup_manager.py
- Backup Launcher: run_database_backup.ps1

## 2. Backup Configuration

Backups are stored in:

```text
backups/
```

Backup naming convention:

```text
ai_learning_planner_YYYYMMDD_HHMMSS.sql
```

The backup manager provides:

- MySQL database export.
- Temporary credential-file handling.
- Backup integrity verification.
- Partial backup cleanup after failures.
- Retention of backups from the latest seven distinct dates.
- Logging of backup execution.

Backup logs:

```text
logs/database_backup.log
logs/scheduled_backup_runner.log
```

The backup directory and logs are excluded from Git.

## 3. Automated Backup Execution

The backup is scheduled through Windows Task Scheduler.

Task name:

```text
AI Learning Planner - Daily Database Backup
```

Schedule:

```text
Daily at 2:00 AM
```

To execute a backup manually, open PowerShell in the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\run_database_backup.ps1"
```

Check the result:

```powershell
Get-ChildItem .\backups\ai_learning_planner_*.sql |
    Sort-Object LastWriteTime -Descending
```

The scheduled task currently uses interactive Windows logon. Windows must have the configured user logged in for the task to execute.

## 4. Selecting a Backup

List available backups:

```powershell
Get-ChildItem .\backups\ai_learning_planner_*.sql |
    Sort-Object LastWriteTime -Descending
```

Select the latest backup:

```powershell
$Backup = Get-ChildItem .\backups\ai_learning_planner_*.sql |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$Backup.FullName
```

Check its size:

```powershell
$Backup.Length
```

Do not restore an empty, incomplete, or unverified backup.

## 5. Verifying Backup Integrity

The backup manager provides the `verify_backup()` function.

Run:

```powershell
& .\.venv\Scripts\python.exe -c "import sys; from pathlib import Path; from app.database.backup_manager import verify_backup; print(verify_backup(Path(sys.argv[1])))" $Backup.FullName
```

The verification checks:

1. Backup file exists.
2. Backup file is not empty.
3. CREATE TABLE statements exist.
4. MySQL dump completion marker exists.

The verification output includes file size, table count and INSERT statement count.

These checks establish basic dump integrity. A successful database restoration is stronger evidence of recoverability.

## 6. Database Restoration

### Important Safety Rules

- Never experiment on the original database.
- Preserve the original SQL backup.
- Restore into a separate database when validating recovery.
- Do not overwrite an existing database without an explicit recovery decision.
- Confirm the target database name before importing.

### Step 1: Create an isolated restore database

Open MySQL using an account with database creation privileges:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

Enter the password when prompted.

Create a separate restore database:

```sql
CREATE DATABASE ai_learning_planner_restore_test;
```

Verify:

```sql
SHOW DATABASES;
```

Exit:

```sql
EXIT;
```

If the database already exists, do not drop it automatically. Inspect it first.

### Step 2: Import the backup

Open Windows Command Prompt (cmd.exe), not PowerShell.

Run the following command after replacing the backup path with the actual selected backup:

```cmd
"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p ai_learning_planner_restore_test < "C:\FULL\PATH\TO\BACKUP.sql"
```

Enter the MySQL password when prompted.

This imports the SQL dump into the isolated restore database.

### Step 3: Verify restored tables

Open MySQL:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

Run:

```sql
USE ai_learning_planner_restore_test;

SHOW TABLES;
```

Check record counts:

```sql
SELECT COUNT(*) FROM students;
SELECT COUNT(*) FROM subjects;
SELECT COUNT(*) FROM topics;
SELECT COUNT(*) FROM performance;
SELECT COUNT(*) FROM study_plans;
SELECT COUNT(*) FROM study_plan_items;
SELECT COUNT(*) FROM quizzes;
SELECT COUNT(*) FROM quiz_questions;
SELECT COUNT(*) FROM quiz_results;
SELECT COUNT(*) FROM quiz_answers;
SELECT COUNT(*) FROM resources;
```

Compare the results with the backup recovery report and the expected application data.

## 7. Previous Recovery Validation

A recovery test was completed on 09 November 2026.

Backup:

```text
backups/ai_learning_planner_20261109_125241.sql
```

Restore database:

```text
ai_learning_planner_restore_test
```

Results:

| Validation | Result |
|---|---|
| Backup verification | PASS |
| Database restoration | PASS |
| Table row counts | 11/11 MATCH |
| Schema comparison | 11/11 MATCH |
| Foreign-key relationships | 16/16 PASS |
| Orphan records | 0 |
| ORM compatibility | PASS |
| FastAPI startup | PASS |
| Router registration | 12/12 PASS |
| Database-backed API tests | 6/6 PASS |

Six selected read-only API endpoints returned HTTP 200.

Authentication was overridden during isolated API testing. Login and JWT authentication were not independently validated by that test.

Detailed evidence:

```text
docs/DATABASE_RECOVERY_REPORT.md
```

## 8. Reconnecting the Application After Recovery

The application database configuration is defined in:

```text
app/core/config.py
app/database/connection.py
```

The production database URL is loaded through:

```python
get_database_url()
```

It validates that the configured database is:

```text
ai_learning_planner
```

After a genuine production recovery:

1. Confirm the intended production database has been restored.
2. Confirm the `.env` DATABASE_URL points to `ai_learning_planner`.
3. Keep database credentials private.
4. Restart the FastAPI application.
5. Confirm database connectivity.
6. Check application logs.
7. Test important application endpoints.

Do not point the production application to the temporary restore-test database.

## 9. Recovery Failure Handling

If restoration fails:

1. Stop the restoration process.
2. Preserve the original backup.
3. Inspect the MySQL error message.
4. Check MySQL server availability.
5. Confirm the selected SQL file is valid.
6. Check database privileges and available disk space.
7. Retry using a separate empty restore database.
8. Verify the restored database before reconnecting the application.

Never delete the original backup as part of troubleshooting.

## 10. Limitations and Future Improvements

Current implementation limitations:

- Backups are stored locally.
- Off-site backup storage has not been configured.
- Recovery validation covered selected read-only APIs.
- POST and PUT endpoints were not tested against the restored database.
- Agent workflows, RAG retrieval and frontend integration were not included in the recovery validation.
- Scheduled execution currently requires interactive Windows logon.

Potential improvements:

- Off-site backup storage.
- Backup encryption.
- Backup restoration automation.
- Recovery point and recovery time objectives.
- Periodic automated restore testing.
- Monitoring and failure notifications.

## 11. Recovery Checklist

- [ ] Select a valid backup.
- [ ] Verify backup integrity.
- [ ] Preserve the original backup file.
- [ ] Create a separate restore database for validation.
- [ ] Import the SQL dump.
- [ ] Verify all expected tables.
- [ ] Compare record counts.
- [ ] Verify schema and foreign-key relationships.
- [ ] Test ORM connectivity.
- [ ] Test application startup and required endpoints.
- [ ] Reconnect production only after successful recovery validation.
- [ ] Record the recovery operation.

---

End of Database Backup and Recovery Guide.
