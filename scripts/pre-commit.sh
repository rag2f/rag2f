#!/usr/bin/env bash
set -euo pipefail

"$VIRTUAL_ENV/bin/pre-commit" run --all-files