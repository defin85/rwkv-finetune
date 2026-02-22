SHELL := bash

.PHONY: bootstrap health prepare-sample

bootstrap:
	./scripts/bootstrap.sh

health:
	./scripts/healthcheck.sh

prepare-sample:
	./scripts/prepare_binidx.sh data/raw/sample.jsonl data/processed/sample

