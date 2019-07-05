FROM python:3.6

ENV LETSENCRYPT_DIR /letsencrypt
ENV GOOGLE_APPLICATION_CREDENTIALS /secrets/gcp.json
ENV APP_HOME /srv/app

WORKDIR $APP_HOME

COPY plugins plugins
COPY main.py main.py

COPY requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/cert_manager.sh /usr/local/bin/cert_manager.sh

RUN chmod +x /usr/local/bin/cert_manager.sh

ENTRYPOINT cert_manager.sh
