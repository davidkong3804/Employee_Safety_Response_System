from prometheus_client import Counter, Gauge

# Counter for safety reports submitted. Labels: status ('safe', 'need_help'), facility
REPORTS_SUBMITTED = Counter(
    "safety_reports_submitted_total",
    "Total number of safety reports submitted",
    ["status", "facility"]
)

# Gauge for active emergency events. Labels: severity ('low', 'medium', 'high', 'critical')
ACTIVE_EVENTS = Gauge(
    "safety_active_events_count",
    "Current number of active emergency events",
    ["severity"]
)

# Counter for Redis cache hits and misses. Labels: op ('hit', 'miss')
CACHE_OPERATIONS = Counter(
    "safety_cache_operations_total",
    "Total number of cache hits and misses",
    ["op"]
)
