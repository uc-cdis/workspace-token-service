#!/bin/bash

nginx
gunicorn -c "/wts/deployment/wsgi/gunicorn.conf.py"
