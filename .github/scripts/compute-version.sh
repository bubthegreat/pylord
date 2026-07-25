#!/usr/bin/env bash
set -euo pipefail
# Compute the next semver version from git tags.
#
# Usage:
#   compute-version.sh   -> next release, e.g. 0.1.2
#
# Releases are what ArgoCD resolves: the prod Application tracks a semver
# range over tags (targetRevision '>=0.1.0'), so pushing tag v0.1.2 is what
# rolls the realm forward. Nothing writes an image tag into a values file
# any more.
#
# Requires all tags to be fetched (actions/checkout with fetch-depth: 0).
BOOTSTRAP_VERSION="0.1.0"

latest=$(git tag --list 'v[0-9]*' \
  | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' \
  | sort -V | tail -n1 || true)

if [[ -z "${latest}" ]]; then
  next="${BOOTSTRAP_VERSION}"
else
  IFS=. read -r major minor patch <<<"${latest#v}"
  next="${major}.${minor}.$((patch + 1))"
fi

echo "${next}"
