FROM docker-registry.tools.wmflabs.org/toolforge-python3.13:latest

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip wheel && \
    /opt/venv/bin/pip install -r /tmp/requirements.txt && \
    /opt/venv/bin/python3 -m spacy download en_core_web_sm

COPY . /opt/app
WORKDIR /opt/app
RUN mkdir -p /opt/app/.cache

EXPOSE 8000
CMD ["/opt/venv/bin/python3", "/opt/app/server.py"]
