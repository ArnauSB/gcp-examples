# Build stage
FROM golang:1.23 AS builder
WORKDIR /app

COPY go.mod ./
RUN go mod download

COPY . ./
RUN go build -o server

# Final image
FROM debian:bookworm-slim
WORKDIR /app

COPY --from=builder /app/server .
COPY static/ ./static/

EXPOSE 8080
CMD ["./server"]
