# Football Match Outcome Prediction

A web app that shows fixtures, results, team statistics, and the probability of a **home win, draw, or away win** for each match. It covers the Premier League by default and can be configured for other domestic leagues.

Predictions cover regular time only. Group stages, cup formats, extra time, and penalty shoot-outs are not supported.

The repository does not include historical data or trained models. You build them with the commands described below.

## Features

- Fixtures, results, and team statistics
- Home win, draw, and away win probabilities for upcoming matches
- A command-line pipeline for data collection, quality checks, features, datasets, and training
- Model versioning with promotion and rollback
- Scheduled data updates
- Metrics and dashboards with Prometheus and Grafana
- Support for several leagues, each with its own data and models

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript |
| API | FastAPI |
| Database | PostgreSQL |
| Machine learning | LightGBM, scikit-learn |
| Monitoring | Prometheus, Grafana |
| Deployment | Docker Compose |

## Requirements

- Docker Engine with Docker Compose v2
- For local development: Python 3.11, PostgreSQL 17, and Node.js 24

## Getting started

The machine learning libraries are large, so check that you have enough disk space before you build the images.

```sh
cp .env.example .env
# Set DB_PASSWORD and GRAFANA_PASSWORD in .env
docker compose up -d --build
docker compose ps
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |
| Liveness check | http://localhost:8000/live |
| Readiness check | http://localhost:8000/ready?league=epl |

Compose starts PostgreSQL, runs the database migrations, and then starts the API and the frontend. All ports listen on `localhost` only.

The data pages work without a model. `/ready` returns `503` until a valid model is active for the league.

For HTTPS, backups, upgrades, and troubleshooting, see the [operations guide](docs/operations.md).

## Building data and models

All steps run through a command-line tool. The examples below run from the project root. If you work inside `backend/` without Docker, replace `docker compose --profile operations run --rm cli` with `python -m football`.

```sh
docker compose --profile operations build cli
docker compose --profile operations run --rm cli --help
```

### Step by step

```sh
docker compose --profile operations run --rm cli ingest --league epl --source sofascore --season-count 7
docker compose --profile operations run --rm cli quality --league epl
docker compose --profile operations run --rm cli features --league epl
docker compose --profile operations run --rm cli dataset --league epl
docker compose --profile operations run --rm cli train --league epl --dataset DATASET_ID
```

`dataset` prints a `dataset_id`. Use it in the `train` command.

### All steps at once

```sh
docker compose --profile operations run --rm cli pipeline run --league epl --source sofascore --season-count 7
docker compose --profile operations run --rm cli pipeline status --league epl
```

The pipeline runs ingest, quality checks, features, dataset, and training in order. Useful options:

| Option | Effect |
| --- | --- |
| `--promote` | Activate the new model if it passes the quality checks |
| `--no-train` | Update data and features only |
| `--seasons 2024/2025 2025/2026` | Use specific seasons (cannot be combined with `--season-count`) |
| `--train-seasons` | Choose which seasons to train on |

### Incremental updates

By default, `ingest` skips finished matches that have not changed. Use `--refresh-days 7` to change the refresh window, or `--mode full` to fetch everything again. Run a full ingest from time to time to pick up corrections to older statistics.

Features are always rebuilt from the full history of the league.

The command-line tool writes JSON to stdout and logs to stderr. It exits with `0` on success, `1` on error, and `130` when interrupted. Only one command can write to the same league at a time.

## Model lifecycle

Training creates a **candidate** model. It does not replace the active model until you promote it.

```sh
docker compose --profile operations run --rm cli model check --league epl --model-version MODEL_VERSION
docker compose --profile operations run --rm cli model promote --league epl --model-version MODEL_VERSION
docker compose --profile operations run --rm cli model status --league epl
docker compose --profile operations run --rm cli model rollback --league epl
```

Promotion checks the release policy in `backend/ml/config/release.json`, file checksums, and the model format. The API picks up the new version on the next request without a restart. Rollback returns to the previously active version.

### How models are built

- Datasets are stored in `backend/data/datasets/<league>/<dataset_id>/` and never change after creation.
- Models are stored in `backend/models/<league>/<version>/`, together with the configuration, library versions, cross-validation results, and a copy of the source code used to train them.
- Training compares a frequency baseline, LightGBM, and a stacked ensemble on the same time-based folds. Calibration uses data that comes after the base model's training window.
- Features for a match use only matches played before that match day. Line-ups that were not known before kick-off are marked as unknown.
- `constraints-ml.txt` pins the ML libraries for both training and the API. A model is rejected if the library versions, features, or output probabilities do not match.
- If you change the feature code, you must train a new model. The API does not run an old model with new feature code.

Only load model files you trust, because `joblib` can execute code.

### Evaluation and drift

```sh
docker compose --profile operations run --rm cli evaluate --league epl --model-version MODEL_VERSION --dataset FUTURE_DATASET_ID
docker compose --profile operations run --rm cli drift --league epl --reference TRAIN_DATASET_ID --current RECENT_DATASET_ID --bins 10 --threshold 0.2
```

The evaluation dataset must come entirely after the training period. The drift report shows the Population Stability Index (PSI) for each feature. A high value is a reason to investigate. It does not prove that the model has become worse.

## Scheduled updates

```sh
docker compose --profile scheduler up -d --build scheduler
docker compose logs -f scheduler
```

The scheduler runs ingest, quality checks, and features. By default, it runs every 6 hours, covers the most recent season, and stops a run after 3 hours. Change these with `SCHEDULE_INTERVAL_SECONDS`, `SCHEDULE_SEASON_COUNT`, and `SCHEDULE_TIMEOUT_SECONDS`. The scheduler never trains or promotes models.

## Adding a league

1. Add a profile to `backend/config/leagues.json` with the league slug, time zone, season type, number of rounds, season phases, winter months, and the league ID for each data source.
2. Copy `backend/ml/config/default.json`, then review the list of strong teams, derbies, and other league-specific settings.
3. Pass the new file with `--config` to the `features`, `dataset`, and `train` commands.

The frontend and API select a league with `?league=SLUG`. A league selector appears when more than one league is configured. Each league needs its own model.

## Data sources

| Source | Notes |
| --- | --- |
| `sofascore` | Default source. Its API is unofficial and may change without notice. |
| `api_football` | Requires `API_FOOTBALL_KEY`. `API_FOOTBALL_MAX_REQUESTS` limits requests per command. |

If a source fails, updates stop, but stored data and models are kept. There is no automatic fallback to another source.

Entities are never matched by name across sources. Before you switch sources, map the external IDs to existing teams and matches with the `identity` command (see `identity --help`).

To add a source, implement the interface in `backend/providers/base/`, convert the data to `ParsedMatchBundle`, and register the adapter in `ProviderRegistry`.

## Monitoring

```sh
docker compose --profile monitoring up -d prometheus grafana
```

Prometheus runs at http://localhost:9090 and Grafana at http://localhost:3001. The API exposes `/metrics` with request latency, job failures, last successful ingest, and model quality over the last 90 days.

Alert rules are in `backend/monitoring/alerts.yml`. Keep `API_WORKERS=1` so that Prometheus collects correct metrics.

Experiment tracking with MLflow is optional. Install `requirements-tracking.txt` (or set `INSTALL_TRACKING=1` before you build the CLI image) and set `MLFLOW_TRACKING_URI`.

## Local development

**Backend** (from `backend/`, inside a virtual environment):

```sh
pip install -r requirements-dev.txt
python -m football migrate
python -m pytest tests -q
uvicorn api.main:app --reload --port 8000
```

Set `TEST_DATABASE_URL` to run the database tests. Use a separate PostgreSQL instance with permission to create databases. Never point it at a production database. Without this variable, the database tests are skipped.

**Frontend** (from `frontend/`):

```sh
npm ci
npm run typecheck
npm run lint
npm test
npm run build
npm run dev
```

The frontend calls the API through `/api` on the same origin. `API_INTERNAL_URL` sets the API address and defaults to `http://localhost:8000`.

## Project structure

```text
backend/
  api/            HTTP API and stored predictions
  config/         League profiles and source settings
  elt_pipeline/   Ingest, change detection, and loading
  ml/             Features, Elo ratings, training, evaluation, inference, model registry
  monitoring/     Metrics, alerts, and dashboards
  operations/     Migrations, quality checks, jobs, scheduler, entity mapping
  providers/      Data source adapters
frontend/         Web interface
docs/             Operations guide
```

## License

MIT. See [LICENSE](LICENSE).
