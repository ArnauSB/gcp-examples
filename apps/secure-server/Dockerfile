FROM python:3.12-slim

WORKDIR /app

# CA in root directory
COPY ca.crt /usr/local/share/ca-certificates/ca.crt

RUN apt-get update && \
    apt-get install -y ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Remember to copy server.crt and server.key from src/
COPY ./src .

EXPOSE 8080

ENTRYPOINT [ "python", "secure_server.py" ]
