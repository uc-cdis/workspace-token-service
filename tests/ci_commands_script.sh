#!/usr/bin/env bash

poetry run pytest -vv --cov=wts --cov-report xml tests
