FROM python:3.11.5-slim

RUN apt-get update && \
    apt-get install -y \
    libpq-dev gcc python3-dev musl-dev && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV SERVER_ADDRESS=localhost:8080
ENV POSTGRES_USERNAME=cnrprod1725804607-team-77833
ENV POSTGRES_PASSWORD=cnrprod1725804607-team-77833
ENV POSTGRES_HOST=rc1b-5xmqy6bq501kls4m.mdb.yandexcloud.net
ENV POSTGRES_PORT=6432
ENV POSTGRES_DATABASE=cnrprod1725804607-team-77833

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENV FLASK_APP=test.py

EXPOSE 8080

CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
