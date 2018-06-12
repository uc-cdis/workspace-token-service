FROM tiangolo/uwsgi-nginx:python3.6-alpine3.7


RUN apk update && apk add bash git postgresql-libs postgresql-dev libffi-dev libressl-dev gcc linux-headers musl-dev

COPY . /workspace-token-service
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/nginx/nginx.conf /etc/nginx/
COPY ./deployment/nginx/uwsgi.conf /etc/nginx/conf.d/
WORKDIR /workspace-token-service

RUN python -m pip install --upgrade pip \
    && python -m pip install --upgrade setuptools \
    && pip install -r requirements.txt --target /usr/local/lib/python3.6/site-packages/

RUN mkdir -p /var/www/workspace-token-service \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/ \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

EXPOSE 80

WORKDIR /var/www/workspace-token-service

CMD /workspace-token-service/dockerrun.bash
