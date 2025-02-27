FROM python:3.12.9-slim-bullseye@sha256:44d4cea0ff1d49f79a5f2b4249cdcb40369e7d4ca8db83dd74bf13c56741a895

WORKDIR /app

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
