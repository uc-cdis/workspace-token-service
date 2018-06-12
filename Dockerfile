# To run: docker run -d -v /path/to/local_settings.py:/var/www/gen3-metadata/local_settings.py --name=gen3-metadata -p 80:80 gen3-metadata
# To check running container: docker exec -it gen3-metadata /bin/bash

FROM ubuntu:16.04
# image for sftp & ssh protocols
FROM atmoz/sftp:debian-jessie

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    build-essential \
    curl \
    git \
    # for ftp
    lftp \
    # for decryption dbgap files
    mcrypt \
    libapache2-mod-wsgi \
    # dependency for cryptography
    libffi-dev \
    # dependency for pyscopg2 - which is dependency for sqlalchemy postgres engine
    libpq-dev \
    # dependency for cryptography
    libssl-dev \
    python3.6 \
    python-dev \
    python3-pip \
    python-setuptools \
    vim \
    && pip3 install pip==9.0.3 \
    && pip3 install --upgrade setuptools \
    && mkdir /var/www/gen3-metadata \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && chown www-data -R /var/www/.cache/Python-Eggs/

COPY . /gen3-metadata
WORKDIR /gen3-metadata
#
# Custom apache24 logging - see http://www.loadbalancer.org/blog/apache-and-x-forwarded-for-headers/
#
RUN ln -s /gen3-metadata/wsgi.py /var/www/gen3-metadata/wsgi.py \
    && pip3 install -r requirements.txt \
    && python setup.py develop \
    && echo '<VirtualHost *:80>\n\
    WSGIDaemonProcess /gen3-metadata processes=1 threads=1 python-path=/var/www/gen3-metadata/:/gen3-metadata/:/usr/bin/python\n\
    WSGIScriptAlias / /var/www/gen3-metadata/wsgi.py\n\
    WSGIPassAuthorization On\n\
    <Directory "/var/www/gen3-metadata/">\n\
        WSGIProcessGroup /gen3-metadata\n\
        WSGIApplicationGroup %{GLOBAL}\n\
        Options +ExecCGI\n\
        Order deny,allow\n\
        Allow from all\n\
    </Directory>\n\
    ErrorLog ${APACHE_LOG_DIR}/error.log\n\
    LogLevel info\n\
    LogFormat "%{X-Forwarded-For}i %l %{X-UserId}i %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\"" aws\n\
    SetEnvIf X-Forwarded-For "^..*" forwarded\n\
    CustomLog ${APACHE_LOG_DIR}/access.log combined env=!forwarded\n\
    CustomLog ${APACHE_LOG_DIR}/access.log aws env=forwarded\n\
</VirtualHost>\n'\
>> /etc/apache2/sites-available/gen3-metadata.conf \
    && a2dissite 000-default \
    && a2ensite gen3-metadata \
    && a2enmod reqtimeout \
    && ln -sf /dev/stdout /var/log/apache2/access.log \
    && ln -sf /dev/stderr /var/log/apache2/error.log

EXPOSE 80
WORKDIR /var/www/gen3-metadata/

CMD rm -f /var/run/apache2/apache2.pid && /usr/sbin/apache2ctl -D FOREGROUND
