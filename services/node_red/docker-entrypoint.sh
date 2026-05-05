#!/bin/sh
set -e
node /usr/local/bin/generate-settings.cjs
exec /usr/src/node-red/entrypoint.sh "$@"
