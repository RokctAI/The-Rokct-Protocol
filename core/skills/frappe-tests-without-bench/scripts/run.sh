#!/bin/bash
# usage: run.sh <polaris/frappe/src dir> <test modules...>
set -e
H=$(cd "$(dirname "$0")" && pwd)
SRC=$1
shift
rm -rf "$H/app"
mkdir -p "$H/app/polaris"
cp -r "$SRC/tenant" "$H/app/polaris/tenant"
touch "$H/app/__init__.py" "$H/app/polaris/__init__.py"
find "$H/app" -name "*.py" -exec sed -i 's/{app_name}/app/g' {} +
cd "$H" && PYTHONPATH="$H/stub:$H" python3 -m unittest "$@" 2>&1 | tail -25
