FROM golang:1.22-alpine AS builder

WORKDIR /src
RUN apk add --no-cache git ca-certificates

COPY go-collector/go.mod go-collector/go.sum ./
RUN go mod download

COPY go-collector/ ./
COPY config/leagues.json /app/config/leagues.json

RUN CGO_ENABLED=0 GOOS=linux go build -o /collector ./cmd/collector

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=builder /collector /app/collector
COPY --from=builder /app/config/leagues.json /app/config/leagues.json

ENV OUTPUT_DIR=/data \
    CONFIG_PATH=/app/config/leagues.json \
    NATS_URL=nats://nats:4222 \
    ETCD_ENDPOINTS=etcd:2379 \
    ARROW_PORT=8815 \
    COLLECT_INTERVAL=30s \
    BATCH_SIZE=15 \
    BATCH_FLUSH=5s \
    WINDOW_SIZE=60s

VOLUME ["/data"]
ENTRYPOINT ["/app/collector"]
