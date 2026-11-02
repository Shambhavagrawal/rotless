#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
# input skills ship as SKILL.md.fixture so repo scanners skip them; restore the real name
find . -name "*.fixture" -type f | while read -r f; do mv "$f" "${f%.fixture}"; done
