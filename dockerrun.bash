#!/bin/bash

nginx
poetry run gunicorn -c "/wts/deployment/wsgi/gunicorn.conf.py"
