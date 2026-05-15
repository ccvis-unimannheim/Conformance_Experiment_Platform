ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

FROM python:3.12-slim

RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

ENV PYTHONPATH=/code:$PYTHONPATH

RUN pip install --no-cache-dir --upgrade pip

COPY ./ProViBackend/requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt --default-timeout=100

RUN apt-get update -y

RUN apt-get install -y graphviz

RUN apt-get install -y curl

COPY ./tests /code/tests

COPY ./ProViBackend /code/ProViBackend

CMD ["fastapi", "run", "ProViBackend/app/main.py", "--proxy-headers", "--port", "80"]
