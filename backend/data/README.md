# Data Directory

This directory holds data files for the Premier League prediction system.

## `raw/`

**DO NOT place CSV files here.** All match data comes from the database via the ELT pipeline.

Any CSV files found in `raw/` are legacy/test data and are gitignored.
The system uses PostgreSQL as its sole source of truth.

