Project selectors for DQC live next to `dbt_project.yml` so `dbt test --selector dqc_all_tests` works without extra flags:

- [`../../dbt/selectors.yml`](../../dbt/selectors.yml) — defines `dqc_all_tests` (see also `monitoring/quality/README.md`).
