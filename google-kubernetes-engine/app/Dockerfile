FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy module files first for layer caching
COPY go.mod ./
RUN go mod download

# Copy source and build a static binary
COPY . ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /webserver

# --- final stage ---
FROM alpine:3.19

RUN adduser -D -g '' appuser

COPY --from=builder /webserver /webserver

USER appuser

EXPOSE 8080

CMD ["/webserver"]
