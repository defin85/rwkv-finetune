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

AIRFLOW_RUNTIME_ROOT="${AIRFLOW_RUNTIME_ROOT:-$ROOT_DIR/orchestration/airflow/runtime}"
AIRFLOW_HOME="${AIRFLOW_HOME:-$AIRFLOW_RUNTIME_ROOT}"
AIRFLOW_DAGS_DIR="${AIRFLOW_DAGS_DIR:-$ROOT_DIR/orchestration/airflow/dags}"
AIRFLOW_PLUGINS_DIR="${AIRFLOW_PLUGINS_DIR:-$ROOT_DIR/orchestration/airflow/plugins}"
AIRFLOW_DB_DIR="${AIRFLOW_DB_DIR:-$AIRFLOW_RUNTIME_ROOT/db}"
AIRFLOW_LOG_DIR="${AIRFLOW_LOG_DIR:-$AIRFLOW_RUNTIME_ROOT/logs}"
AIRFLOW_PID_DIR="${AIRFLOW_PID_DIR:-$AIRFLOW_RUNTIME_ROOT/pids}"
AIRFLOW_AUDIT_DIR="${AIRFLOW_AUDIT_DIR:-$AIRFLOW_RUNTIME_ROOT/audit}"
AIRFLOW_WEBSERVER_PORT="${AIRFLOW_WEBSERVER_PORT:-8080}"
AIRFLOW_DAG_ID="${AIRFLOW_DAG_ID:-rwkv_train_lifecycle}"
AIRFLOW_VERSION="${AIRFLOW_VERSION:-2.10.5}"
AIRFLOW_GPU_POOL_NAME="${AIRFLOW_GPU_POOL_NAME:-rwkv_gpu_pool}"
AIRFLOW_GPU_POOL_SLOTS="${AIRFLOW_GPU_POOL_SLOTS:-1}"
AIRFLOW_SUPPORTED_PYTHON_MIN="${AIRFLOW_SUPPORTED_PYTHON_MIN:-3.9}"
AIRFLOW_SUPPORTED_PYTHON_MAX="${AIRFLOW_SUPPORTED_PYTHON_MAX:-3.12}"

export AIRFLOW_HOME
export AIRFLOW__CORE__LOAD_EXAMPLES="${AIRFLOW__CORE__LOAD_EXAMPLES:-False}"
export AIRFLOW__CORE__DAGS_FOLDER="${AIRFLOW__CORE__DAGS_FOLDER:-$AIRFLOW_DAGS_DIR}"
export AIRFLOW__CORE__PLUGINS_FOLDER="${AIRFLOW__CORE__PLUGINS_FOLDER:-$AIRFLOW_PLUGINS_DIR}"
export AIRFLOW__CORE__EXECUTOR="${AIRFLOW__CORE__EXECUTOR:-LocalExecutor}"
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-sqlite:///$AIRFLOW_DB_DIR/airflow.db}"
export AIRFLOW__LOGGING__BASE_LOG_FOLDER="${AIRFLOW__LOGGING__BASE_LOG_FOLDER:-$AIRFLOW_LOG_DIR/airflow}"

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
