# To run: docker run -v /path/to/wsgi.py:/var/www/wts/wsgi.py --name=wts -p 81:80 wts
# To check running container: docker exec -it wts /bin/bash

FROM quay.io/cdis/python:python3.9-buster-2.0.0


ENV appname=wts

COPY . /$appname
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/uwsgi/wsgi.py /$appname/wsgi.py
WORKDIR /$appname

RUN pip install --upgrade pip
RUN pip install --upgrade poetry

COPY poetry.lock pyproject.toml /$appname/
RUN poetry config virtualenvs.create false \
    && poetry install -vv --no-dev --no-interaction \
    && poetry show -v

RUN mkdir -p /var/www/$appname \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/ \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && chown nginx -R /var/www/.cache/Python-Eggs/ \
    && chown nginx /var/www/$appname

# py httpx in authlib wants to access $HOME/.netrc -
# there is nothing secret in /root
RUN touch /root/.netrc && chmod -R a+rX /root

EXPOSE 80

WORKDIR /var/www/$appname

CMD /dockerrun.sh
