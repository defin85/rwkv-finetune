#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

ORCHESTRATION_PROFILE="${ORCHESTRATION_PROFILE:-airflow}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CUDA_HOME="${CUDA_HOME:-/opt/cuda}"

AIRFLOW_RUNTIME_ROOT="${AIRFLOW_RUNTIME_ROOT:-$ROOT_DIR/orchestration/airflow/runtime}"
AIRFLOW_HOME="${AIRFLOW_HOME:-$AIRFLOW_RUNTIME_ROOT}"
AIRFLOW_DAGS_DIR="${AIRFLOW_DAGS_DIR:-$ROOT_DIR/orchestration/airflow/dags}"
AIRFLOW_PLUGINS_DIR="${AIRFLOW_PLUGINS_DIR:-$ROOT_DIR/orchestration/airflow/plugins}"
AIRFLOW_DB_DIR="${AIRFLOW_DB_DIR:-$AIRFLOW_RUNTIME_ROOT/db}"
AIRFLOW_LOG_DIR="${AIRFLOW_LOG_DIR:-$AIRFLOW_RUNTIME_ROOT/logs}"
AIRFLOW_PID_DIR="${AIRFLOW_PID_DIR:-$AIRFLOW_RUNTIME_ROOT/pids}"
AIRFLOW_AUDIT_DIR="${AIRFLOW_AUDIT_DIR:-$AIRFLOW_RUNTIME_ROOT/audit}"
AIRFLOW_WEBSERVER_PORT="${AIRFLOW_WEBSERVER_PORT:-18080}"
AIRFLOW_DAG_ID="${AIRFLOW_DAG_ID:-rwkv_train_lifecycle}"
AIRFLOW_VERSION="${AIRFLOW_VERSION:-2.10.5}"
AIRFLOW_GPU_POOL_NAME="${AIRFLOW_GPU_POOL_NAME:-rwkv_gpu_pool}"
AIRFLOW_GPU_POOL_SLOTS="${AIRFLOW_GPU_POOL_SLOTS:-1}"
AIRFLOW_SUPPORTED_PYTHON_MIN="${AIRFLOW_SUPPORTED_PYTHON_MIN:-3.9}"
AIRFLOW_SUPPORTED_PYTHON_MAX="${AIRFLOW_SUPPORTED_PYTHON_MAX:-3.12}"
AIRFLOW_WEBSERVER_CONFIG_FILE="${AIRFLOW_WEBSERVER_CONFIG_FILE:-$ROOT_DIR/orchestration/airflow/webserver_config.py}"
AIRFLOW_RATELIMIT_STORAGE_URI="${AIRFLOW_RATELIMIT_STORAGE_URI:-memory://}"

export AIRFLOW_HOME
export AIRFLOW_RUNTIME_ROOT
export AIRFLOW_DAGS_DIR
export AIRFLOW_PLUGINS_DIR
export AIRFLOW_DB_DIR
export AIRFLOW_LOG_DIR
export AIRFLOW_PID_DIR
export AIRFLOW_AUDIT_DIR
export AIRFLOW_WEBSERVER_PORT
export AIRFLOW_DAG_ID
export AIRFLOW_VERSION
export AIRFLOW_GPU_POOL_NAME
export AIRFLOW_GPU_POOL_SLOTS
export CUDA_HOME
if [ -d "$CUDA_HOME/bin" ]; then
  export PATH="$CUDA_HOME/bin:$PATH"
fi
if [ -d "$CUDA_HOME/lib64" ]; then
  if [ -n "${LD_LIBRARY_PATH:-}" ]; then
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64:$LD_LIBRARY_PATH"
  else
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64"
  fi
fi
export AIRFLOW__CORE__LOAD_EXAMPLES="${AIRFLOW__CORE__LOAD_EXAMPLES:-False}"
export AIRFLOW__CORE__DAGS_FOLDER="${AIRFLOW__CORE__DAGS_FOLDER:-$AIRFLOW_DAGS_DIR}"
export AIRFLOW__CORE__PLUGINS_FOLDER="${AIRFLOW__CORE__PLUGINS_FOLDER:-$AIRFLOW_PLUGINS_DIR}"
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-sqlite:///$AIRFLOW_DB_DIR/airflow.db}"
if [ -z "${AIRFLOW__CORE__EXECUTOR:-}" ]; then
  case "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" in
    sqlite:*)
      # LocalExecutor is incompatible with SQLite in Airflow 2.x.
      export AIRFLOW__CORE__EXECUTOR="SequentialExecutor"
      ;;
    *)
      export AIRFLOW__CORE__EXECUTOR="LocalExecutor"
      ;;
  esac
else
  export AIRFLOW__CORE__EXECUTOR
fi
export AIRFLOW__CORE__AUTH_MANAGER="${AIRFLOW__CORE__AUTH_MANAGER:-airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager}"
export AIRFLOW__WEBSERVER__CONFIG_FILE="${AIRFLOW__WEBSERVER__CONFIG_FILE:-$AIRFLOW_WEBSERVER_CONFIG_FILE}"
export AIRFLOW__WEBSERVER__SHOW_TRIGGER_FORM_IF_NO_PARAMS="${AIRFLOW__WEBSERVER__SHOW_TRIGGER_FORM_IF_NO_PARAMS:-True}"
export AIRFLOW__LOGGING__BASE_LOG_FOLDER="${AIRFLOW__LOGGING__BASE_LOG_FOLDER:-$AIRFLOW_LOG_DIR/airflow}"
export RATELIMIT_STORAGE_URI="${RATELIMIT_STORAGE_URI:-$AIRFLOW_RATELIMIT_STORAGE_URI}"

# Optional DAG defaults consumed in rwkv_train_lifecycle.py via _conf_or_env().
# Export only non-empty values to avoid overriding DAG defaults with empty strings.
[ -n "${RWKV_AIRFLOW_RUN_NAME:-}" ] && export RWKV_AIRFLOW_RUN_NAME
[ -n "${RWKV_AIRFLOW_INPUT_JSONL:-}" ] && export RWKV_AIRFLOW_INPUT_JSONL
[ -n "${RWKV_AIRFLOW_OUTPUT_PREFIX:-}" ] && export RWKV_AIRFLOW_OUTPUT_PREFIX
[ -n "${RWKV_AIRFLOW_DATA_PREFIX:-}" ] && export RWKV_AIRFLOW_DATA_PREFIX
[ -n "${RWKV_AIRFLOW_LOAD_MODEL:-}" ] && export RWKV_AIRFLOW_LOAD_MODEL
[ -n "${RWKV_AIRFLOW_DEVICES:-}" ] && export RWKV_AIRFLOW_DEVICES
[ -n "${RWKV_AIRFLOW_WANDB_PROJECT:-}" ] && export RWKV_AIRFLOW_WANDB_PROJECT
[ -n "${RWKV_AIRFLOW_TRAIN_WRAPPER:-}" ] && export RWKV_AIRFLOW_TRAIN_WRAPPER
[ -n "${RWKV_AIRFLOW_DATASET_MANIFEST:-}" ] && export RWKV_AIRFLOW_DATASET_MANIFEST
[ -n "${RWKV_AIRFLOW_DATASET_QUALITY_STATUS:-}" ] && export RWKV_AIRFLOW_DATASET_QUALITY_STATUS
[ -n "${RWKV_AIRFLOW_DOMAIN_EVAL_VERDICT:-}" ] && export RWKV_AIRFLOW_DOMAIN_EVAL_VERDICT
[ -n "${RWKV_AIRFLOW_RETENTION_EVAL_VERDICT:-}" ] && export RWKV_AIRFLOW_RETENTION_EVAL_VERDICT
[ -n "${RWKV_AIRFLOW_EVAL_SUMMARY_PATH:-}" ] && export RWKV_AIRFLOW_EVAL_SUMMARY_PATH
[ -n "${RWKV_AIRFLOW_RELEASE_MANIFEST_PATH:-}" ] && export RWKV_AIRFLOW_RELEASE_MANIFEST_PATH

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_runtime_dirs() {
  mkdir -p \
    "$AIRFLOW_DAGS_DIR" \
    "$AIRFLOW_PLUGINS_DIR" \
    "$AIRFLOW_DB_DIR" \
    "$AIRFLOW_LOG_DIR" \
    "$AIRFLOW_PID_DIR" \
    "$AIRFLOW_AUDIT_DIR"
}

activate_venv_if_present() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
  fi
}

validate_orchestration_profile() {
  case "$ORCHESTRATION_PROFILE" in
    airflow|mlops-lite)
      ;;
    *)
      echo "Unsupported ORCHESTRATION_PROFILE: $ORCHESTRATION_PROFILE" >&2
      echo "Supported values: airflow, mlops-lite" >&2
      exit 1
      ;;
  esac
}

require_primary_airflow() {
  validate_orchestration_profile
  if [ "$ORCHESTRATION_PROFILE" != "airflow" ]; then
    echo "Invalid primary orchestration profile: $ORCHESTRATION_PROFILE" >&2
    echo "Current policy requires ORCHESTRATION_PROFILE=airflow." >&2
    exit 1
  fi
}
