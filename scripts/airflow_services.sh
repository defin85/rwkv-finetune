#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/airflow_common.sh"

SERVICE_LOG_DIR=""
SCHEDULER_PID_FILE=""
WEBSERVER_PID_FILE=""
WEB_PROCESS_LABEL="webserver"

has_subcommand() {
  local cmd="$1"
  airflow "$cmd" --help >/dev/null 2>&1
}

init_paths() {
  ensure_runtime_dirs
  SERVICE_LOG_DIR="$AIRFLOW_LOG_DIR/services"
  mkdir -p "$SERVICE_LOG_DIR"
  SCHEDULER_PID_FILE="$AIRFLOW_PID_DIR/scheduler.pid"
  WEBSERVER_PID_FILE="$AIRFLOW_PID_DIR/webserver.pid"
}

is_running() {
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return 1
  fi
  local pid
  pid="$(cat "$pid_file")"
  if [ -z "$pid" ]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

start_services() {
  need_cmd airflow
  init_paths

  if ! is_running "$SCHEDULER_PID_FILE"; then
    airflow scheduler \
      --daemon \
      --pid "$SCHEDULER_PID_FILE" \
      --stdout "$SERVICE_LOG_DIR/scheduler.out" \
      --stderr "$SERVICE_LOG_DIR/scheduler.err"
  fi

  if ! is_running "$WEBSERVER_PID_FILE"; then
    if has_subcommand webserver; then
      WEB_PROCESS_LABEL="webserver"
      airflow webserver \
        --daemon \
        --port "$AIRFLOW_WEBSERVER_PORT" \
        --pid "$WEBSERVER_PID_FILE" \
        --stdout "$SERVICE_LOG_DIR/webserver.out" \
        --stderr "$SERVICE_LOG_DIR/webserver.err"
    else
      WEB_PROCESS_LABEL="api-server"
      airflow api-server \
        --daemon \
        --port "$AIRFLOW_WEBSERVER_PORT" \
        --pid "$WEBSERVER_PID_FILE" \
        --stdout "$SERVICE_LOG_DIR/webserver.out" \
        --stderr "$SERVICE_LOG_DIR/webserver.err"
    fi
  fi
}

stop_service_by_pid() {
  local pid_file="$1"
  if ! is_running "$pid_file"; then
    rm -f "$pid_file"
    return 0
  fi
  local pid
  pid="$(cat "$pid_file")"
  kill "$pid"
  for _ in $(seq 1 20); do
    if kill -0 "$pid" >/dev/null 2>&1; then
      sleep 0.2
    else
      break
    fi
  done
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -9 "$pid"
  fi
  rm -f "$pid_file"
}

stop_services() {
  init_paths
  stop_service_by_pid "$SCHEDULER_PID_FILE"
  stop_service_by_pid "$WEBSERVER_PID_FILE"
}

status_services() {
  init_paths
  if is_running "$SCHEDULER_PID_FILE"; then
    echo "scheduler: running (pid $(cat "$SCHEDULER_PID_FILE"))"
  else
    echo "scheduler: stopped"
  fi

  if is_running "$WEBSERVER_PID_FILE"; then
    if has_subcommand webserver; then
      WEB_PROCESS_LABEL="webserver"
    else
      WEB_PROCESS_LABEL="api-server"
    fi
    echo "$WEB_PROCESS_LABEL: running (pid $(cat "$WEBSERVER_PID_FILE"), port $AIRFLOW_WEBSERVER_PORT)"
  else
    echo "webserver/api-server: stopped"
  fi
}

usage() {
  cat <<'EOF'
Usage:
  airflow_services.sh <start|stop|restart|status>
EOF
}

if [ "$#" -ne 1 ]; then
  usage
  exit 1
fi

require_primary_airflow
activate_venv_if_present

case "$1" in
  start)
    start_services
    status_services
    ;;
  stop)
    stop_services
    status_services
    ;;
  restart)
    stop_services
    start_services
    status_services
    ;;
  status)
    status_services
    ;;
  *)
    usage
    exit 1
    ;;
esac
