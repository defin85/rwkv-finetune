SHELL := bash

.PHONY: bootstrap health prepare-sample airflow-ci airflow-smoke-strict

bootstrap:
	./scripts/bootstrap.sh

health:
	./scripts/healthcheck.sh

prepare-sample:
	./scripts/prepare_binidx.sh data/raw/sample.jsonl data/processed/sample

airflow-ci:
	./scripts/airflow_ci_checks.sh

airflow-smoke-strict:
	./scripts/airflow_smoke.sh --mode strict
