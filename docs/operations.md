# Operations Guide

This guide covers deployment, upgrades, backups, troubleshooting, and monitoring.

## Preparing the environment

- Decide where Docker stores its data before you build the images. On Docker Desktop, check the disk image location under Resources. Do not move the disk image while Docker is running.
- Use a separate Compose project and PostgreSQL volume for each environment, such as staging, production, and testing.
- Check free disk space with `docker system df`. Never use `docker system prune`, `docker volume prune`, or `docker compose down -v` as part of a deployment.
- Create `backend/models`, `backend/data/datasets`, and `backend/logs`, and give the job container user write access to them. On Linux, find the user and group IDs with `docker compose --profile operations run --rm --entrypoint id cli`, then set permissions on these folders only. Do not use `chmod 777`.
- Serve the frontend through a reverse proxy with HTTPS. Keep PostgreSQL and the monitoring tools on an internal network.
- The API has no user accounts. Protect the admin interfaces and any endpoints that write data at the proxy level, and set request limits and timeouts there.
- Store the `.env` file in a secrets manager. Never put API keys, passwords, or connection strings in logs, artifacts, or Git.

## Upgrading

1. Stop the scheduler and any running jobs. Wait until all locks are released.
2. Back up the database, models, datasets, and configuration as described below. Check that the backup can be read.
3. Check out the release you want to deploy, run `docker compose config --quiet`, and build the images.
4. Run the `migrate` service and check its log and the `SchemaMigrations` table. If the checksum of an applied migration has changed, find out why before you continue. Never edit the migration table to hide the difference.
5. Start the API and the frontend. Check `/live`, `/health`, the data pages, and `/ready?league=epl`.
6. If the feature code or configuration has changed, rebuild the features and train a new candidate model. The API refuses to serve a model whose features do not match.
7. Promote a model only after you have reviewed its evaluation results, the data, and the release policy. Then restart the scheduler.

To restore an older schema, use a backup instead of trying to reverse migrations.

Each league has a single set of computed features. If you rebuild features with a new configuration on the live database, the active model stops serving until a matching model is promoted. Build and evaluate new feature configurations in a separate environment first.

## Backup and restore

Store backups outside the database volume and keep a copy on another device or storage service. Use a unique file name for each backup:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/epl-backup.dump'
docker compose cp postgres:/tmp/epl-backup.dump backups/epl-backup.dump
docker compose exec -T postgres rm /tmp/epl-backup.dump
```

Never overwrite your most recent good backup. Run `pg_restore --list` on the dump to check its format, and practice a restore on a separate empty database. In Windows PowerShell 5, do not redirect a binary dump with `>`, because it can corrupt the file.

Back up these together:

- The database: matches, ID mappings, snapshots, feature builds, job history, predictions, and the active model pointer
- `backend/models/`: models, manifests, and source bundles, including the current and previous versions
- `backend/data/datasets/`: the datasets used for training and evaluation
- The application release, the league, ML, and release configuration, and your secrets, stored separately

To restore, create a separate environment with its own volume. Restore the database into an empty database with `pg_restore`, copy back the model and dataset folders, and run the checksum and readiness checks. Compare `ModelDeployments` with the model versions on disk. Switch traffic only after these checks pass. Never test a restore on the live database.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Data cannot be fetched | Source logs, HTTP status codes, quota, API key, and response format. Do not retry repeatedly if access is denied. |
| A command reports that another job is running | `pipeline status`, running processes, and database locks. Do not remove locks or end sessions you do not own. |
| A job stays `RUNNING` after its process has stopped | The next command for the same league marks it `INTERRUPTED` once it gets the lock. Run an incremental ingest again. |
| A source returns incomplete secondary data | `IngestionObservations.component_status` and the raw `IngestionSnapshots`. Partial or unavailable data never deletes existing data. |
| Corrected historical data does not appear | Run ingest with `--mode full`, then `quality` and `features`. Incremental ingest cannot detect changes when the match summary stays the same. |
| `/ready` returns 503 | Database connection, promoted model, checksums, Python and library versions, league profile, and feature build freshness. |
| Prediction quality drops | Sample size, season and team distribution, source coverage, and drift. Evaluate on a separate future dataset before you replace the model. |

If a season has an unexpected number of matches, compare it with the official schedule. The `quality` command checks that the stored data is consistent. It does not check whether the source returned every match.

## Monitoring and alerts

The `monitoring` profile is optional. Prometheus keeps up to 15 days or about 1 GB of data. Container logs rotate at 10 MB, with three files per container. Images, build cache, the database, and model files need additional space.

Available metrics:

- HTTP: request rate, errors, and latency
- Pipeline: last successful ingest, failed jobs in the last 24 hours, age of running jobs, and latest source observation
- Active model: number of matched pre-match predictions over 90 days, log loss, and accuracy. These metrics are empty until results are available.
- `football_monitoring_available=0`: the collector cannot read the database. Treat this as an error, not as a quiet period.

The default alert thresholds are a starting point. Adjust them to your season calendar, update schedule, and benchmarks. Alertmanager is not included. To receive alerts, configure a notification channel and send a test alert from staging. The HTTP dashboard is included in Grafana, and you can query the ML metrics directly in Prometheus or Grafana.

## Storage and retention

Do not delete raw snapshots, datasets, or models automatically. Base your retention policy on what you need to reproduce results and on storage cost. Before you delete anything:

1. Keep the active model, the previous version, and any version you may need to audit.
2. Keep the datasets used by those models and by any report that refers to them.
3. Archive raw snapshots before you shorten their history. Without them, you cannot compare later source corrections.
4. Clear the build cache for this project only, and only after you confirm which images and artifacts to keep. Do not clean up Docker resources for the whole machine.

## Go-live checklist

Before you serve real traffic, confirm that you have:

- Run the tests on PostgreSQL, built the frontend, and checked the API both with and without a model
- Used a real data source with valid usage rights and enough quota, and checked the historical seasons against official records
- Trained and evaluated a model on real data with time-based validation and a future holdout set, and compared it with the baseline and its calibration
- Practiced promotion, rollback, restore from backup, scheduler interruption, and alert delivery
- Tested the Linux images, bind mount permissions, secrets, TLS, resources, and load in the target environment

Results from synthetic test data do not replace any of these checks.
