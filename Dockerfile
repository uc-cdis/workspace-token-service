# To run: docker run -v /path/to/wsgi.py:/var/www/wts/wsgi.py --name=wts -p 81:80 wts
# To check running container: docker exec -it wts /bin/bash


FROM quay.io/cdis/python:pybase3-2.0.1


ENV appname=wts

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libmcrypt4 libmhash2 mcrypt \
    curl bash git vim \
    && apt-get clean

COPY . /$appname
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/uwsgi/wsgi.py /$appname/wsgi.py
WORKDIR /$appname

RUN python -m pip install --upgrade pip \
    && pip install pipenv \
    && python -m pipenv install --system --deploy --ignore-pipfile \
    && pip freeze

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

RUN COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >$appname/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>$appname/version_data.py \
    && python setup.py install

WORKDIR /var/www/$appname

CMD /dockerrun.sh
