#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv312}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
GGUF_CONVERTER="${RWKV_GGUF_CONVERTER:-/tmp/rwkv-convert/convert_rwkv_pth_to_gguf.py}"
GGUF_VOCAB="${RWKV_GGUF_VOCAB:-/tmp/rwkv-convert/rwkv_vocab_v20230424.txt}"
WINDOWS_POWERSHELL="${WINDOWS_POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"

RUN_INPUT=""
MODEL_NAME=""
OUTTYPE="f16"
FORCE_CONVERT=0
SKIP_INSTALL=0

usage() {
  cat <<EOF
Usage:
  package_run_for_ollama_windows.sh --run <runs/<name>|<name>|/abs/path> [options]

Options:
  --run <path|name>         Run directory path or run name from runs/.
  --model-name <name>       Ollama model name (default: rwkv7-<run-name>).
  --outtype <f16|bf16|f32>  GGUF outtype for converter (default: f16).
  --force-convert           Rebuild GGUF even if it already exists.
  --skip-install            Do not install into Windows Ollama automatically.
  -h, --help                Show this help.

Example:
  ./scripts/package_run_for_ollama_windows.sh --run airflow-20260224T154017
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --run)
      RUN_INPUT="$2"
      shift 2
      ;;
    --model-name)
      MODEL_NAME="$2"
      shift 2
      ;;
    --outtype)
      OUTTYPE="$2"
      shift 2
      ;;
    --force-convert)
      FORCE_CONVERT=1
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=1
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

if [ -z "$RUN_INPUT" ]; then
  usage
  exit 1
fi

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

activate_venv_if_present() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
  fi
}

sanitize_model_name() {
  local value="$1"
  value="$(echo "$value" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//')"
  if [ -z "$value" ]; then
    echo "rwkv7-model"
  else
    echo "$value"
  fi
}

resolve_run_dir() {
  local input="$1"
  if [ -d "$input" ]; then
    realpath "$input"
    return
  fi
  if [ -d "$ROOT_DIR/runs/$input" ]; then
    realpath "$ROOT_DIR/runs/$input"
    return
  fi
  echo "Run directory not found for input: $input" >&2
  exit 1
}

to_unc_backslash_path() {
  local linux_path="$1"
  local distro="${WSL_DISTRO_NAME:-archlinux}"
  local with_backslashes="${linux_path//\//\\}"
  printf '\\\\wsl.localhost\\%s%s' "$distro" "$with_backslashes"
}

to_unc_slash_path() {
  local backslash_path
  backslash_path="$(to_unc_backslash_path "$1")"
  printf '%s' "${backslash_path//\\//}"
}

ensure_python_deps() {
  "$PYTHON_BIN" - <<'PY'
import importlib
mods = ["torch", "numpy", "gguf"]
missing = []
for mod in mods:
    try:
        importlib.import_module(mod)
    except Exception:
        missing.append(mod)
if missing:
    raise SystemExit("missing:" + ",".join(missing))
PY
}

build_manifest() {
  local run_dir="$1"
  local pth_path="$2"
  local gguf_path="$3"
  local run_name="$4"
  local model_name="$5"
  local outtype="$6"
  local converter="$7"
  local vocab="$8"
  local out_path="$run_dir/model_manifest.json"
  local release_manifest_path="$run_dir/release_manifest.json"

  "$PYTHON_BIN" - "$run_dir" "$pth_path" "$gguf_path" "$run_name" "$model_name" "$outtype" "$converter" "$vocab" "$out_path" "$release_manifest_path" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    run_dir,
    pth_path,
    gguf_path,
    run_name,
    model_name,
    outtype,
    converter,
    vocab,
    out_path,
    release_manifest_path,
) = sys.argv[1:11]

run_dir_path = Path(run_dir)
pth = Path(pth_path)
gguf = Path(gguf_path)
out = Path(out_path)
release_path = Path(release_manifest_path)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

release = {}
if release_path.exists():
    release = json.loads(release_path.read_text(encoding="utf-8"))

payload = {
    "manifest_version": 1,
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "run_name": run_name,
    "ollama_model_name": model_name,
    "artifacts": {
        "source_checkpoint": {
            "path": str(pth.resolve()),
            "sha256": sha256(pth),
            "size_bytes": pth.stat().st_size,
            "format": "pth",
        },
        "gguf": {
            "path": str(gguf.resolve()),
            "sha256": sha256(gguf),
            "size_bytes": gguf.stat().st_size,
            "format": "gguf",
            "outtype": outtype,
            "converter": converter,
            "vocab": vocab,
        },
    },
    "release": {
        "status": release.get("status", "unknown"),
        "overall_verdict": release.get("overall_verdict", "unknown"),
        "release_manifest_path": str(release_path.resolve()) if release_path.exists() else "",
    },
}

out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(out)
PY
}

generate_modelfiles() {
  local run_dir="$1"
  local gguf_path="$2"
  local gguf_unc_slash="$3"
  local linux_modelfile="$run_dir/Modelfile.ollama"
  local windows_modelfile="$run_dir/Modelfile.windows.slash.chatfix.ollama"

  cat >"$linux_modelfile" <<EOF
FROM $gguf_path

PARAMETER temperature 0.7
PARAMETER top_p 0.6
PARAMETER repeat_penalty 1.3
PARAMETER repeat_last_n 256
PARAMETER num_predict 128
EOF

  cat >"$windows_modelfile" <<EOF
FROM $gguf_unc_slash

TEMPLATE """{{- if .System }}System: {{ .System }}

{{- end }}{{- range .Messages -}}
{{- if eq .Role "user" }}User: {{ .Content }}

{{- else if eq .Role "assistant" }}Assistant: {{ .Content }}

{{- end -}}
{{- end }}Assistant:"""

PARAMETER stop "\\nUser:"
PARAMETER stop "\\nSystem:"
PARAMETER temperature 0.7
PARAMETER top_p 0.6
PARAMETER repeat_penalty 1.3
PARAMETER repeat_last_n 256
PARAMETER num_predict 128
EOF
}

generate_windows_installer() {
  local run_dir="$1"
  local run_name="$2"
  local model_name="$3"
  local gguf_unc_backslash="$4"
  local installer="$run_dir/install_ollama_windows.ps1"

  cat >"$installer" <<EOF
param(
  [string]\$ModelName = "$model_name"
)

\$ErrorActionPreference = "Stop"

\$srcGguf = "$gguf_unc_backslash"
if (-not (Test-Path \$srcGguf)) {
  throw "GGUF not found: \$srcGguf"
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  throw "ollama command not found in PATH"
}

\$dstDir = Join-Path \$env:USERPROFILE ".ollama\\imports\\$run_name"
\$dstGguf = Join-Path \$dstDir "rwkv-0.gguf"
\$dstModelfile = Join-Path \$dstDir "Modelfile"

New-Item -ItemType Directory -Force -Path \$dstDir | Out-Null
Copy-Item -Path \$srcGguf -Destination \$dstGguf -Force

\$ggufPathForModelfile = \$dstGguf -replace "\\\\", "/"
\$modelfile = @"
FROM \$ggufPathForModelfile

TEMPLATE """{{- if .System }}System: {{ .System }}

{{- end }}{{- range .Messages -}}
{{- if eq .Role "user" }}User: {{ .Content }}

{{- else if eq .Role "assistant" }}Assistant: {{ .Content }}

{{- end -}}
{{- end }}Assistant:"""

PARAMETER stop "\nUser:"
PARAMETER stop "\nSystem:"
PARAMETER temperature 0.7
PARAMETER top_p 0.6
PARAMETER repeat_penalty 1.3
PARAMETER repeat_last_n 256
PARAMETER num_predict 128
"@

Set-Content -Path \$dstModelfile -Value \$modelfile -Encoding UTF8
ollama create \$ModelName -f \$dstModelfile
Write-Host "Installed model: \$ModelName"
Write-Host "Run: ollama run \$ModelName \"кто ты?\""
EOF
}

install_on_windows() {
  local installer_linux="$1"
  local model_name="$2"
  local installer_unc
  installer_unc="$(to_unc_backslash_path "$installer_linux")"

  if [ ! -x /init ]; then
    echo "/init is not available; cannot launch Windows PowerShell from this WSL session." >&2
    exit 1
  fi
  if [ ! -f "$WINDOWS_POWERSHELL" ]; then
    echo "Windows PowerShell not found: $WINDOWS_POWERSHELL" >&2
    exit 1
  fi

  /init "$WINDOWS_POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$installer_unc" -ModelName "$model_name"
}

need_cmd realpath
need_cmd sed
need_cmd "$PYTHON_BIN"
activate_venv_if_present

RUN_DIR="$(resolve_run_dir "$RUN_INPUT")"
RUN_NAME="$(basename "$RUN_DIR")"
PTH_PATH="$RUN_DIR/rwkv-0.pth"
GGUF_PATH="$RUN_DIR/rwkv-0.gguf"

if [ ! -f "$PTH_PATH" ]; then
  echo "Checkpoint not found: $PTH_PATH" >&2
  exit 1
fi
if [ ! -f "$GGUF_CONVERTER" ]; then
  echo "GGUF converter not found: $GGUF_CONVERTER" >&2
  exit 1
fi
if [ ! -f "$GGUF_VOCAB" ]; then
  echo "GGUF vocab not found: $GGUF_VOCAB" >&2
  exit 1
fi

if [ -z "$MODEL_NAME" ]; then
  MODEL_NAME="$(sanitize_model_name "rwkv7-$RUN_NAME")"
else
  MODEL_NAME="$(sanitize_model_name "$MODEL_NAME")"
fi

if [ "$FORCE_CONVERT" = "1" ] || [ ! -f "$GGUF_PATH" ]; then
  echo "Building GGUF: $GGUF_PATH"
  if ! ensure_python_deps >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip install --quiet numpy gguf
  fi
  "$PYTHON_BIN" "$GGUF_CONVERTER" "$PTH_PATH" "$GGUF_VOCAB" --outfile "$GGUF_PATH" --outtype "$OUTTYPE"
else
  echo "GGUF already exists, reuse: $GGUF_PATH"
fi

GGUF_UNC_BACKSLASH="$(to_unc_backslash_path "$GGUF_PATH")"
GGUF_UNC_SLASH="$(to_unc_slash_path "$GGUF_PATH")"

generate_modelfiles "$RUN_DIR" "$GGUF_PATH" "$GGUF_UNC_SLASH"
generate_windows_installer "$RUN_DIR" "$RUN_NAME" "$MODEL_NAME" "$GGUF_UNC_BACKSLASH"
build_manifest "$RUN_DIR" "$PTH_PATH" "$GGUF_PATH" "$RUN_NAME" "$MODEL_NAME" "$OUTTYPE" "$GGUF_CONVERTER" "$GGUF_VOCAB" >/dev/null

echo "Packaged run: $RUN_NAME"
echo "  GGUF: $GGUF_PATH"
echo "  Manifest: $RUN_DIR/model_manifest.json"
echo "  Linux Modelfile: $RUN_DIR/Modelfile.ollama"
echo "  Windows Modelfile: $RUN_DIR/Modelfile.windows.slash.chatfix.ollama"
echo "  Windows installer: $RUN_DIR/install_ollama_windows.ps1"
echo "  Ollama model name: $MODEL_NAME"

if [ "$SKIP_INSTALL" = "1" ]; then
  echo "Skip Windows install (--skip-install)."
else
  echo "Installing model into Windows Ollama..."
  install_on_windows "$RUN_DIR/install_ollama_windows.ps1" "$MODEL_NAME"
fi
