#!/usr/bin/env bash
set -euo pipefail

mkdir -p vendor

FULL_CLONE=${VENDOR_FULL_CLONE:-0}
if [[ "${1:-}" == "--full" ]]; then
  FULL_CLONE=1
fi

clone_or_update() {
  local url="$1"; shift
  local dir="$1"; shift
  if [ -d "vendor/$dir/.git" ]; then
    echo "[update] $dir"
    git -C "vendor/$dir" pull --ff-only || true
  else
    echo "[clone] $dir <- $url"
    if [[ "$FULL_CLONE" == "1" ]]; then
      git clone "$url" "vendor/$dir"
    else
      git clone --depth 1 "$url" "vendor/$dir"
    fi
  fi
}

clone_or_update https://github.com/hudson-and-thames/mlfinlab.git mlfinlab
clone_or_update https://github.com/quantopian/alphalens.git alphalens
clone_or_update https://github.com/robertmartin8/PyPortfolioOpt.git PyPortfolioOpt
clone_or_update https://github.com/dcajasn/Riskfolio-Lib.git riskfolio-lib

echo "Done."
if [[ "$FULL_CLONE" == "1" ]]; then
  echo "(full clone mode)"
else
  echo "(shallow clone mode)"
fi
