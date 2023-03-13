#!/bin/bash -e

set -x
./scripts/check.sh

uvicorn tests.server:app --log-level critical --port 7575 &

while [[ ! $(curl http://127.0.0.1:7575) ]]; do
  sleep 0.5
done

pytest --doctest-modules --doctest-glob="*md" docs

if ps -p $PID > /dev/null
then
  kill -9 $!
fi

pytest