"""
Centralised Prometheus business-metric registry for the HACCP Control platform.

All custom metrics are defined here as module-level singletons and imported
directly by the service functions that emit them.  Defining metrics in one
place prevents duplicate-registration errors if modules are imported multiple
times during startup (a Prometheus client invariant).

Design decisions
----------------
- **No ``establishment_id`` labels**: would create an unbounded label cardinality
  (one time-series per establishment × metric).  Use Loki log queries for
  per-establishment analysis.
- **Histograms over Summaries**: histograms allow server-side aggregation across
  multiple replicas; summaries are computed client-side and cannot be merged.
- **Counters never decrease**: total counts are always counters; compute rates
  with PromQL ``rate()`` or ``increase()``.
"""

from prometheus_client import Counter, Histogram

# ── Temperature records ───────────────────────────────────────────────────────

TEMPERATURE_RECORDS_TOTAL = Counter(
    "haccp_temperature_records_total",
    "Total HACCP temperature measurements recorded.",
    ["is_conforme", "source"],
)
"""Counter incremented for every ``ReleveTemperature`` created.

Labels:
    is_conforme: ``"true"`` or ``"false"`` — whether the reading was within
        the equipment's target range.
    source: ``"MANUEL"`` or ``"IOT"`` — how the reading was captured.
"""

TEMPERATURE_RECORD_DURATION_SECONDS = Histogram(
    "haccp_temperature_record_duration_seconds",
    "End-to-end latency of create_temperature_record() including NC creation.",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
"""Histogram for the wall-clock time of a full temperature record creation.

Includes both the DB write and the optional non-conformity creation that
happens in the same transaction when ``is_conforme=False``.
"""

# ── Non-conformities ──────────────────────────────────────────────────────────

NONCONFORMITIES_OPENED_TOTAL = Counter(
    "haccp_nonconformities_opened_total",
    "Total non-conformity tickets opened.",
    ["workflow_type"],
)
"""Counter incremented whenever a new NonConformity is opened.

Labels:
    workflow_type: ``"TEMPERATURE"`` (auto) or ``"RECEPTION"`` (manual).
"""

NONCONFORMITIES_RESOLVED_TOTAL = Counter(
    "haccp_nonconformities_resolved_total",
    "Total non-conformity tickets resolved (corrective action submitted).",
    ["workflow_type"],
)
"""Counter incremented when a corrective action moves a NC to RESOLVED."""

NONCONFORMITIES_CLOSED_TOTAL = Counter(
    "haccp_nonconformities_closed_total",
    "Total non-conformity tickets closed (manager sign-off).",
)
"""Counter incremented when a manager closes a NC."""

NONCONFORMITY_RESOLUTION_SECONDS = Histogram(
    "haccp_nonconformity_resolution_seconds",
    "Time elapsed between NC opening and corrective-action submission.",
    # Buckets from 5 min up to 48 h — covers fast field fixes and slow escalations.
    buckets=[300, 900, 1800, 3600, 7200, 14400, 43200, 86400, 172800],
    labelnames=["workflow_type"],
)
"""Histogram measuring how quickly operators resolve non-conformities."""

# ── Reception sessions ────────────────────────────────────────────────────────

RECEPTION_SESSIONS_OPENED_TOTAL = Counter(
    "haccp_reception_sessions_opened_total",
    "Total supplier delivery reception sessions opened.",
)
"""Counter incremented when a new ReceptionSession is created."""

RECEPTION_SESSIONS_CLOSED_TOTAL = Counter(
    "haccp_reception_sessions_closed_total",
    "Total reception sessions closed (delivery confirmed).",
)
"""Counter incremented when a session transitions to CLOSED."""

RECEPTION_ITEMS_TOTAL = Counter(
    "haccp_reception_items_total",
    "Total reception items scanned.",
    ["is_compliant"],
)
"""Counter incremented for each ReceptionItem added.

Labels:
    is_compliant: ``"true"`` or ``"false"``.
"""

# ── Cleaning logs ─────────────────────────────────────────────────────────────

CLEANING_LOGS_TOTAL = Counter(
    "haccp_cleaning_logs_total",
    "Total cleaning task execution logs recorded.",
    ["status"],
)
"""Counter incremented for each CleaningLog entry in a bulk submission.

Labels:
    status: ``"DONE"`` or ``"ISSUE"``.
"""

# ── Time-clock / operator presence ───────────────────────────────────────────
# Note: A Gauge for currently-clocked-in operators (haccp_operators_clocked_in)
# is planned but requires a startup probe to initialise from existing pointages.
# Use the timeclock events counter + PromQL delta for now.

TIMECLOCK_EVENTS_TOTAL = Counter(
    "haccp_timeclock_events_total",
    "Total operator time-clock events recorded.",
    ["type_evenement"],
)
"""Counter incremented for each Pointage event.

Labels:
    type_evenement: one of ``"CLOCK_IN"``, ``"BREAK_START"``,
        ``"BREAK_END"``, ``"CLOCK_OUT"``.
"""
