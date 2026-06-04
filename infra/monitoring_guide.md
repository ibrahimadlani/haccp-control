# Monitoring, Alerting And Run Guide

This guide covers operational observability for the HACCP FastAPI backend.

## Local Observability Stack

Start the local stack:

```bash
docker compose up --build
```

Local endpoints:

- API health: `http://localhost:8001/health`
- API metrics: `http://localhost:8001/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Default local Grafana credentials:

```text
admin / admin
```

Override them locally:

```bash
GRAFANA_PORT=3001 GRAFANA_ADMIN_USER=admin GRAFANA_ADMIN_PASSWORD=change-me docker compose up
```

## Sentry Error Alerting

Sentry is disabled unless `SENTRY_DSN` is present. Production should set:

```text
SENTRY_DSN=<project-dsn>
ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05
SENTRY_PROFILES_SAMPLE_RATE=0.0
```

Recommended Sentry alert rules:

1. Open the Sentry project.
2. Go to `Alerts` -> `Create Alert` -> `Issues`.
3. Create a rule named `Backend repeated SQLAlchemy errors`.
4. Filter:
   - Event type: error.
   - Exception type contains `SQLAlchemyError`.
5. Trigger:
   - More than `5` events in `5 minutes`.
6. Actions:
   - Send email to the on-call backend group.
   - Send Slack webhook to `#haccp-prod-alerts`.

Create a second alert named `Backend repeated S3 upload errors`:

- Exception type or message contains `S3`, `ClientError`, `upload_fileobj`, or `botocore`.
- Trigger when more than `5` events occur in `5 minutes`.
- Notify the same on-call channel.

Operational policy:

- Treat repeated SQLAlchemy errors as potential data-plane incidents.
- Treat repeated S3 upload errors as degraded document/photo capture.
- Include request context and release SHA in Sentry releases when adding deployment automation.

## Prometheus Metrics

The API exposes Prometheus metrics at `/metrics` through `prometheus-fastapi-instrumentator`.

Key metrics to watch:

- `http_requests_total` or generated request-count metrics from the FastAPI instrumentator.
- Request latency histogram buckets, especially p95 and p99.
- 5xx error rate by handler and method.
- `/health` availability from an external blackbox probe.
- Process memory and CPU if collected from ECS, EC2, or Kubernetes exporters.
- PostgreSQL RDS CPU, connections, free storage, read/write latency, and deadlocks.

Useful PromQL examples:

5xx rate:

```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

p99 latency:

```promql
histogram_quantile(
  0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, handler, method)
)
```

Request throughput:

```promql
sum(rate(http_requests_total[1m])) by (handler, method)
```

## Grafana Alerting

Recommended dashboards:

- API latency by route.
- API request volume by route and method.
- API error rate by status code.
- RDS connections and CPU.
- S3 upload error count from logs/Sentry.

Recommended alerts:

### API 5xx Rate

Trigger when:

```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m])) > 0.02
```

For: `5m`.

Severity: warning. Escalate to critical if above `0.05` for `5m`.

### p99 Latency

Trigger when:

```promql
histogram_quantile(
  0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
) > 1.5
```

For: `10m`.

Severity: warning.

### Health Endpoint Degraded

For production, use a Prometheus blackbox exporter or managed uptime check against:

```text
https://api.saas-haccp.fr/health
```

Trigger when the probe fails:

```promql
probe_success{job="haccp-api-health"} == 0
```

For: `2m`.

Severity: critical.

If only internal Prometheus scraping is available, alert when API targets are down:

```promql
up{job="haccp-api"} == 0
```

For: `1m`.

## Production Runbook

When an alert fires:

1. Check `/health` and ALB target health.
2. Open Sentry and inspect the latest grouped exception.
3. Check CloudWatch logs for the same request ID or timestamp.
4. Check RDS metrics: CPU, connection saturation, storage, locks.
5. Check recent deployments and the ECR image SHA.
6. Roll back to the previous image tag if the incident correlates with deployment.

Minimum incident data to capture:

- Start time and end time.
- Impacted endpoints.
- Error rate and p99 latency.
- Sentry issue links.
- Deployment SHA.
- Mitigation and follow-up actions.
