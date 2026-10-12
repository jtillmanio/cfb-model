# Restore the production database from a backup

Use this when production's database is lost or damaged. Each night the **Backup** workflow
(`.github/workflows/backup.yml`) dumps production, restores the dump into a scratch Postgres,
checks it, and only then stores it in R2 as `backups/<UTC date>.dump`. So every stored dump has
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
   variable, `cfb-backups`) › `backups/`. Names are UTC dates, so the last one listed is the newest.
   Open the matching night's **Backup** run in GitHub Actions: its summary lists every table's row
   count, which step 6 checks against.
2. **Download it** from the dashboard (the object's **Download**) to `restore.dump`. With an R2
   API token instead:
   ```powershell
   aws s3 cp s3://cfb-backups/backups/<date>.dump .\restore.dump --endpoint-url https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
   ```
3. **Make the new database.** Neon › the project › Branches › **Create branch**, named
   `restore/<date>`, from `main` (or from any branch if `main` is gone). Open its **Connect**
   dialog and copy two connection strings: the **pooled** one (host ends `-pooler`) and the
   **direct** one (pooling off).
4. **Restore the dump** into it. `--clean --if-exists` first drops whatever the branch already
   holds, so the result is exactly the dump:
   ```powershell
   pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error --dbname "<direct URL>" .\restore.dump
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
7. **Let the read-only backup role read it again.** `--no-privileges` dropped its grants. As the
   owner role, in the Neon SQL editor on the new branch:
   ```sql
   GRANT USAGE ON SCHEMA public TO backup_reader;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_reader;
   GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO backup_reader;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO backup_reader;
   ```
8. **Point production at it.**
   - Vercel › Settings › Environment Variables › **Production**: `DATABASE_URL` = the pooled
     URL, `DATABASE_URL_UNPOOLED` = the direct URL.
   - Vercel › Settings › Environment Variables › **Preview**: `PRODUCTION_DATABASE_HOST` = the new
     direct host, so preview builds keep refusing to migrate production (D-100).
   - GitHub › Settings › Secrets and variables › Actions: `PRODUCTION_DATABASE_URL_UNPOOLED` =
     the direct URL (the release workflow), and `BACKUP_DATABASE_URL` = `backup_reader`'s direct
     URL on the new branch (the backup workflow).
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
