"""Konstanten für die Waidly-Revier-Integration."""

DOMAIN = "waidly_revier"

# Öffentliche Web-Revier-API (nur lesend, code-authentifiziert).
API_URL = "https://oylxomwmjidzujimhqcs.supabase.co/functions/v1/web-revier"
# Öffentlicher Supabase-Anon-Key (identisch mit dem der Web-App app.waidly.de).
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im95bHhvbXdtamlkenVqaW1ocWNzIiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NzQ4ODc1ODYsImV4cCI6MjA5MDQ2MzU4Nn0."
    "IJawEkZ5DkGMXLm-gjz5_ZoWnX-PAV3trCakYuAaA48"
)

CONF_CODE = "code"
CONF_INACTIVITY_DAYS = "inactivity_days"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 900  # 15 Minuten (refresh ist günstig, kein Rate-Limit)
DEFAULT_INACTIVITY_DAYS = 14
SESSION_MAX_AGE_HOURS = 23  # vor Ablauf (24h) proaktiv neu validieren

MANUFACTURER = "Waidly"

# HA-Events (Bus) für Automationen.
EVENT_NEUE_ERLEGUNG = "waidly_neue_erlegung"
EVENT_NEUER_ANBLICK = "waidly_neuer_anblick"
EVENT_EINRICHTUNG_WARTUNG = "waidly_einrichtung_wartung"
