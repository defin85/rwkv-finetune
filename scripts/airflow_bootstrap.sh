#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/airflow_common.sh"

SKIP_INSTALL=0
SKIP_ADMIN_USER=0

usage() {
  cat <<'EOF'
Usage:
  airflow_bootstrap.sh [--skip-install] [--skip-admin-user]

Options:
  --skip-install     Do not install apache-airflow via pip
  --skip-admin-user  Do not create/update the default admin account
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --skip-admin-user)
      SKIP_ADMIN_USER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_primary_airflow
need_cmd "$PYTHON_BIN"
activate_venv_if_present
ensure_runtime_dirs

if [ "$SKIP_INSTALL" = "0" ]; then
  PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')"
  AIRFLOW_CONSTRAINT_URL="${AIRFLOW_CONSTRAINT_URL:-https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt}"
  echo "Installing apache-airflow==${AIRFLOW_VERSION} (python ${PYTHON_VERSION})"
  python -m pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "$AIRFLOW_CONSTRAINT_URL"
fi

need_cmd airflow

if airflow db migrate >/dev/null 2>&1; then
  airflow db migrate
else
  airflow db init
fi

airflow pools set "$AIRFLOW_GPU_POOL_NAME" "$AIRFLOW_GPU_POOL_SLOTS" "Serialize GPU-bound train/eval tasks"

if [ "${AIRFLOW_CREATE_ADMIN:-1}" = "1" ] && [ "$SKIP_ADMIN_USER" = "0" ]; then
  AIRFLOW_ADMIN_USERNAME="${AIRFLOW_ADMIN_USERNAME:-admin}"
  AIRFLOW_ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-admin}"
  AIRFLOW_ADMIN_FIRSTNAME="${AIRFLOW_ADMIN_FIRSTNAME:-RWKV}"
  AIRFLOW_ADMIN_LASTNAME="${AIRFLOW_ADMIN_LASTNAME:-Ops}"
  AIRFLOW_ADMIN_EMAIL="${AIRFLOW_ADMIN_EMAIL:-admin@example.local}"

  if airflow users --help >/dev/null 2>&1; then
    if ! airflow users list | awk '{print $2}' | grep -qx "$AIRFLOW_ADMIN_USERNAME"; then
      airflow users create \
        --username "$AIRFLOW_ADMIN_USERNAME" \
        --password "$AIRFLOW_ADMIN_PASSWORD" \
        --firstname "$AIRFLOW_ADMIN_FIRSTNAME" \
        --lastname "$AIRFLOW_ADMIN_LASTNAME" \
        --role Admin \
        --email "$AIRFLOW_ADMIN_EMAIL"
    fi
  else
    echo "Skipping admin user bootstrap: 'airflow users' command is not available in this Airflow version."
  fi
fi

echo "Airflow bootstrap complete."
echo "Next:"
echo "  ./scripts/airflow_services.sh start"
echo "  ./scripts/run_pipeline.sh --help"
