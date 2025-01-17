FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

RUN apt-get update

COPY ./requirements.txt ./requirements.txt

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY ./app /app

RUN apt-get clean autoclean &&\
    apt-get autoremove --yes &&\
    rm -rf /var/lib/{apt,dpkg,cache,log}/
