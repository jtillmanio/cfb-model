# Restore the production database from a backup

Use this when production's database is lost or damaged. Each night the **Backup** workflow
(`.github/workflows/backup.yml`) dumps production, restores the dump into a scratch Postgres,
checks it, and only then stores it in R2 as `backups/daily/<UTC date>.dump` (plus
`backups/weekly/` on a Sunday and `backups/monthly/` on the 1st, D-124). So every stored dump has
already been restored once.

- **Target:** the app works again within **2 hours** of starting (recovery time, D-092). Write
  down the time you start.
- **Data you lose:** up to 24 hours, everything since the last nightly dump (recovery point,
  D-092). Reference data (teams, games, lines) can be rebuilt from the lake; contest entries,
  adjustments and live picks made since the dump can't (02 › What's reproducible and what isn't).
- **Try Neon first:** if the damage is newer than Neon's own history window (the project's
  restore window in the Neon console), Neon › Branches › `main` › Restore to a time just before
  it is faster than this runbook. Use this runbook when that window doesn't reach back far enough.

You need: the Neon, Vercel and Cloudflare dashboards; this repo with `uv` set up; a PostgreSQL
client of the same major version as `PG_MAJOR` (`.github/actions/start-postgres/action.yml`) for
`pg_restore` and `psql`.

## Steps

1. **Find the newest dump.** Cloudflare › R2 › the backup bucket (the `R2_BUCKET` repository
   variable, `cfb-backups`) › `backups/daily/`. Names are UTC dates, so the last one listed is the
   newest; this folder keeps the last 14 days.
   - **The damage is older than that** (or every daily dump already holds it): go to
     `backups/weekly/` (Sundays, kept 90 days), then `backups/monthly/` (the 1st, kept 365 days),
     and pick the newest dump from before the damage started. A missed Sunday or 1st has no copy;
     take the one before it.
   - Flat `backups/<date>.dump` objects directly under `backups/` are from before the tiers; treat
     them like daily dumps until the owner deletes them.

   Open the matching night's **Backup** run in GitHub Actions: its summary lists every table's row
   count, which step 6 checks against.
2. **Download it** from the dashboard (the object's **Download**) to `restore.dump`. With an R2
   API token instead (R2 needs the region `auto` and rejects the CLI's default checksums):
   ```powershell
   $env:AWS_ACCESS_KEY_ID = "<R2 access key ID>"; $env:AWS_SECRET_ACCESS_KEY = "<R2 secret>"
   $env:AWS_DEFAULT_REGION = "auto"
   $env:AWS_REQUEST_CHECKSUM_CALCULATION = "when_required"; $env:AWS_RESPONSE_CHECKSUM_VALIDATION = "when_required"
   aws s3 cp s3://cfb-backups/backups/<daily|weekly|monthly>/<date>.dump .\restore.dump --endpoint-url https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
   ```
3. **Make an empty database.** Neon › the project › Branches › **Create branch**, named
   `restore/<date>`, from `main` (or from any branch if `main` is gone). A branch copies its
   parent's data, damage included, so restore into a new database on it instead: the branch ›
   Databases › **New database**, named `restored`, owned by the same owner role as `neondb`
   (`neondb_owner`). Open **Connect** for that database and copy two connection strings: the
   **pooled** one (host ends `-pooler`) and the **direct** one (pooling off).
4. **Restore the dump** into the empty database, as that owner role. The app connects as the
   same role, so `--no-owner --no-privileges` leaves it owning, and able to read, everything:
   ```powershell
   pg_restore --no-owner --no-privileges --exit-on-error --dbname "<direct URL>" .\restore.dump
   ```
5. **Re-apply the views** from the code production runs. Find production's commit (Vercel ›
   Deployments › the one marked Current, or `/api/py/health` if it answers), then:
   ```powershell
   git switch --detach <commit>
   # .env.live (gitignored) holds one line: PRODUCTION_DATABASE_URL_UNPOOLED=<direct URL>
   uv --directory python run python -m db migrate --target live --env-file ..\.env.live
   git switch main
   ```
   That brings the schema to that commit's migration head (a no-op when the dump is already
   there) and re-applies `python/db/views/*.sql`.
6. **Check the row counts** match the backup run's summary:
   ```powershell
   psql "<direct URL>" -c "SELECT table_schema || '.' || table_name AS t, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text::int AS rows FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1"
   ```
7. **Let the read-only backup role read it.** The branch copied `backup_reader` from its parent,
   but `--no-privileges` restored no table grants. Role membership survives, so in the Neon SQL
   editor on the new branch (as the owner role) make sure it holds Postgres's read-everything role,
   which covers every table and sequence, including future ones:
   ```sql
   GRANT pg_read_all_data TO backup_reader;
   ```
8. **Point production at it.**
   - Vercel › Settings › Environment Variables › **Production**: `DATABASE_URL` = the pooled
     URL, `DATABASE_URL_UNPOOLED` = the direct URL.
   - Vercel › Settings › Environment Variables › **Preview**: `PRODUCTION_DATABASE_HOST` = the new
     direct host, so preview builds keep refusing to migrate production (D-100).
   - GitHub › Settings › Secrets and variables › Actions: `PRODUCTION_DATABASE_URL_UNPOOLED` =
     the direct URL (the release workflow), and `BACKUP_DATABASE_URL` = `backup_reader`'s direct
     URL to the `restored` database (the backup workflow).
   - Vercel › Deployments › the Current production deployment › **Redeploy**: environment
     variables apply only to a new deployment. It rebuilds the same commit.
9. **Check it's live.** Open `<production URL>/api/py/health`: `db_reachable` is `true`,
   `migration_head` is the head from step 5, and `commit` is production's. Sign in on your phone
   and open Teams.
10. **Afterwards.** Run **Backup** by hand (Actions › Backup › Run workflow) to confirm the new
    database backs up. Delete `.env.live` or empty it. Add a row to the log below with the time
    taken. Then decide what to do with the old `main` branch in Neon; don't delete it until the
    restored database has had one good nightly backup.

## Restore log

Fill in after every restore, drills included. If a restore took longer than 2 hours, say which
step was slow and fix this runbook.

| Date | Drill or real | Dump restored | Time taken | Notes |
|---|---|---|---|---|
| | | | | |
