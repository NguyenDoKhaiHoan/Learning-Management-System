# WBS 7.8 — Hardening checkpoint and observability

The API exposes low-cardinality Prometheus text at `/metrics` when
`METRICS_ENABLED=true`. It contains route templates, status counts and total
request duration only; request bodies, query strings, tokens and credentials are
never included. Existing `X-Trace-ID` JSON logs correlate API and worker actions.

Release review must record: migration head, full test command and result, backup
manifest checksum plus restore row-count comparison, file scanner mode, SMTP
delivery mode, and open risks with an owner and next action. The checkpoint is a
quality gate and does not claim production SLA from local timings.
