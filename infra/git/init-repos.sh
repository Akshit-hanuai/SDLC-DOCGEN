#!/bin/sh
# Initialise a bare repo for the git-daemon export and serve it.
# Volumes: /repos holds bare repositories (one per project + one for docs).
set -e

REPOS_ROOT=${REPOS_ROOT:-/repos}
DOCS_REPO=${DOCS_REPO:-sdlc-documents.git}

mkdir -p "$REPOS_ROOT"
cd "$REPOS_ROOT"

if [ ! -d "$DOCS_REPO" ]; then
  git init --bare "$DOCS_REPO"
fi

exec git daemon --reuseaddr --export-all --base-path="$REPOS_ROOT" "$REPOS_ROOT"
