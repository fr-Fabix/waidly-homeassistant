"""Reine Datenverarbeitung für die Waidly-Revier-Integration.

Bewusst OHNE Home-Assistant-Abhängigkeiten gehalten, damit die
Aggregations-Logik (Jagdjahr-Strecke, Einrichtungs-Zustände, …)
eigenständig — auch gegen die Live-API — getestet werden kann.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

# Zustände, die als "Wartung nötig" gelten (alles außer einwandfrei/Gut/leer).
GOOD_STATES = {"gut", "sehr gut", "neu", "ok", ""}

# Einrichtungstypen, die als Wildkamera zählen.
CAMERA_TYPES = {"Wildkamera"}


def jagdjahr_start(today: date) -> date:
    """Beginn des aktuellen Jagdjahres (1. April). DE: 1.4.–31.3."""
    year = today.year if today.month >= 4 else today.year - 1
    return date(year, 4, 1)


def jagdjahr_label(start: date) -> str:
    """z. B. '2026/27' für ein Jagdjahr, das am 1.4.2026 beginnt."""
    return f"{start.year}/{str(start.year + 1)[-2:]}"


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_utc(value: datetime | None) -> datetime | None:
    """Macht ein datetime zeitzonenbewusst (naive Werte gelten als UTC)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class Einrichtung:
    """Eine geteilte Einrichtung/Kanzel inkl. abgeleiteter Felder."""

    raw: dict[str, Any]
    erlegungen_count: int = 0  # via spot_id verknüpfte Erlegungen
    geeignet: bool | None = None  # bei aktueller Windrichtung geeignet (None = unbekannt)

    @property
    def id(self) -> str:
        return str(self.raw.get("id") or self.raw.get("local_spot_id"))

    @property
    def name(self) -> str:
        return self.raw.get("name") or self.typ or "Einrichtung"

    @property
    def typ(self) -> str:
        return self.raw.get("type") or "Sonstiges"

    @property
    def zustand(self) -> str:
        return (self.raw.get("zustand") or "").strip() or "Unbekannt"

    @property
    def needs_maintenance(self) -> bool:
        z = (self.raw.get("zustand") or "").strip().lower()
        if not z:
            return False  # leer = unbekannt, nicht als Defekt werten
        return z not in GOOD_STATES

    @property
    def is_camera(self) -> bool:
        return self.typ in CAMERA_TYPES

    def geeignet_bei(self, current_wind: str | None) -> bool | None:
        """True, wenn die aktuelle Windrichtung zu den geeigneten passt."""
        wg = (self.raw.get("suitable_wind_directions") or "").strip()
        if not current_wind or not wg:
            return None
        dirs = [d.strip().upper() for d in wg.split(",") if d.strip()]
        return current_wind.strip().upper() in dirs

    def attributes(self) -> dict[str, Any]:
        r = self.raw
        return {
            "typ": self.typ,
            "zustand": self.zustand,
            "wartung_noetig": self.needs_maintenance,
            "wind_geeignet": r.get("suitable_wind_directions") or None,
            "geeignet_jetzt": self.geeignet,
            "hoehe_m": r.get("hoehe"),
            "ueberdacht": r.get("is_covered"),
            "kapazitaet": r.get("kapazitaet"),
            "baujahr": r.get("baujahr"),
            "material": r.get("material") or None,
            "beschreibung": r.get("beschreibung") or None,
            "notizen": r.get("notizen") or None,
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "foto_url": r.get("photo_url") or None,
            "erlegungen_von_hier": self.erlegungen_count,
            "aktualisiert": r.get("updated_at"),
        }


@dataclass
class Sperrflaeche:
    """Eine geteilte Sperrflaeche (nicht bejagbare Flaeche) inkl. Gueltigkeit."""

    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.raw.get("id") or self.raw.get("local_sperrflaeche_id"))

    @property
    def name(self) -> str:
        return (self.raw.get("name") or "").strip() or "Sperrfläche"

    @property
    def grund(self) -> str:
        return (self.raw.get("grund") or "").strip() or "Unbekannt"

    @property
    def color_hex(self) -> str | None:
        return (self.raw.get("color_hex") or "").strip() or None

    @property
    def dauerhaft(self) -> bool:
        return bool(self.raw.get("dauerhaft"))

    @property
    def gueltig_von(self) -> str | None:
        return self.raw.get("gueltig_von") or None

    @property
    def gueltig_bis(self) -> str | None:
        return self.raw.get("gueltig_bis") or None

    def is_active(self, now: datetime | None = None) -> bool:
        """Aktiv, wenn dauerhaft oder jetzt (UTC) im Gueltigkeitszeitraum liegt.

        Fehlende/leere Grenzen werden tolerant als offen behandelt: fehlt
        `gueltig_von`, gilt nach unten keine Grenze, fehlt `gueltig_bis`,
        keine nach oben. Zeitangaben ohne Zeitzone werden als UTC gewertet.
        """
        if self.dauerhaft:
            return True
        now = now or datetime.now(timezone.utc)
        von = _as_utc(_parse_dt(self.raw.get("gueltig_von")))
        bis = _as_utc(_parse_dt(self.raw.get("gueltig_bis")))
        if von is not None and now < von:
            return False
        if bis is not None and now > bis:
            return False
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "grund": self.grund,
            "color_hex": self.color_hex,
            "dauerhaft": self.dauerhaft,
            "gueltig_von": self.gueltig_von,
            "gueltig_bis": self.gueltig_bis,
            "aktiv": self.is_active(),
        }


@dataclass
class RevierState:
    """Aggregierter Zustand eines Reviers, von den Entities gelesen."""

    revier: dict[str, Any]
    jagdjahr: str
    all_entries: list[dict[str, Any]] = field(default_factory=list)
    # Strecke (Erlegungen) im laufenden Jagdjahr
    strecke_total: int = 0
    strecke_by_wildart: dict[str, int] = field(default_factory=dict)
    wildbret_kg: float = 0.0
    erloes: float = 0.0
    # Anblicke (Sichtungen) im laufenden Jagdjahr
    anblicke_total: int = 0
    anblicke_by_wildart: dict[str, int] = field(default_factory=dict)
    # Letzte Ereignisse
    letzte_erlegung: dict[str, Any] | None = None
    letzte_aktivitaet: datetime | None = None
    letztes_foto_url: str | None = None
    # Einrichtungen
    einrichtungen: list[Einrichtung] = field(default_factory=list)
    einrichtungen_by_type: dict[str, int] = field(default_factory=dict)
    wartung_count: int = 0
    wartung_liste: list[dict[str, str]] = field(default_factory=list)
    wildkamera_count: int = 0
    # Wind-Eignung (gegen konfigurierte Windrichtungs-Entität)
    current_wind: str | None = None
    geeignete_einrichtungen: list[str] = field(default_factory=list)
    # Sperrflächen (nicht bejagbare Flächen)
    sperrflaechen: list[Sperrflaeche] = field(default_factory=list)
    aktive_sperrflaechen_count: int = 0
    # Inaktivität
    tage_seit_aktivitaet: int | None = None


def compute_revier_state(
    raw: dict[str, Any],
    *,
    today: date | None = None,
    current_wind: str | None = None,
) -> RevierState:
    """Wandelt die rohe `validate`-Antwort in einen aggregierten RevierState."""
    today = today or datetime.now(timezone.utc).date()
    jj_start = jagdjahr_start(today)
    jj_label = jagdjahr_label(jj_start)

    revier = raw.get("revier") or {}
    spots = raw.get("spots") or []
    entries = raw.get("entries") or []
    sperrflaechen = raw.get("sperrflaechen") or []

    state = RevierState(revier=revier, jagdjahr=jj_label, all_entries=list(entries))

    # --- Einrichtungen ---
    # Erlegungen je spot_id zählen (für "erlegungen_von_hier")
    harvests_per_spot: Counter = Counter()
    for e in entries:
        if e.get("entry_type") == "Erlegung" and e.get("spot_id"):
            harvests_per_spot[e["spot_id"]] += int(e.get("anzahl") or 1)

    for s in spots:
        ein = Einrichtung(raw=s, erlegungen_count=harvests_per_spot.get(s.get("id"), 0))
        state.einrichtungen.append(ein)
        state.einrichtungen_by_type[ein.typ] = (
            state.einrichtungen_by_type.get(ein.typ, 0) + 1
        )
        if ein.needs_maintenance:
            state.wartung_count += 1
            state.wartung_liste.append({"name": ein.name, "zustand": ein.zustand})
        if ein.is_camera:
            state.wildkamera_count += 1

    # Wind-Eignung je Einrichtung gegen die aktuelle Windrichtung
    state.current_wind = current_wind
    for ein in state.einrichtungen:
        ein.geeignet = ein.geeignet_bei(current_wind)
    state.geeignete_einrichtungen = [e.name for e in state.einrichtungen if e.geeignet]

    # --- Sperrflächen (nicht bejagbare Flächen) ---
    now_utc = datetime.now(timezone.utc)
    for sp in sperrflaechen:
        flaeche = Sperrflaeche(raw=sp)
        state.sperrflaechen.append(flaeche)
        if flaeche.is_active(now_utc):
            state.aktive_sperrflaechen_count += 1

    # --- Einträge (Erlegungen + Anblicke) ---
    erlegungen = [e for e in entries if e.get("entry_type") == "Erlegung"]
    anblicke = [e for e in entries if e.get("entry_type") == "Anblick"]

    def _entry_sort_key(e: dict[str, Any]) -> tuple[date, datetime]:
        return (
            _parse_date(e.get("datum")) or date.min,
            _parse_dt(e.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        )

    # Strecke + Wildbret + Erlös (nur laufendes Jagdjahr)
    for e in erlegungen:
        e_date = _parse_date(e.get("datum"))
        if e_date is None or e_date < jj_start:
            continue
        anzahl = int(e.get("anzahl") or 1)
        wildart = e.get("wildart") or "Unbekannt"
        state.strecke_total += anzahl
        state.strecke_by_wildart[wildart] = (
            state.strecke_by_wildart.get(wildart, 0) + anzahl
        )
        if e.get("gewicht"):
            state.wildbret_kg += _num(e.get("gewicht")) * anzahl
        state.erloes += _num(e.get("erloes"))

    # Anblicke (nur laufendes Jagdjahr)
    for e in anblicke:
        e_date = _parse_date(e.get("datum"))
        if e_date is None or e_date < jj_start:
            continue
        anzahl = int(e.get("anzahl") or 1)
        wildart = e.get("wildart") or "Unbekannt"
        state.anblicke_total += anzahl
        state.anblicke_by_wildart[wildart] = (
            state.anblicke_by_wildart.get(wildart, 0) + anzahl
        )

    # Letzte Erlegung (über alle Jagdjahre) + zugehöriges Foto
    if erlegungen:
        state.letzte_erlegung = max(erlegungen, key=_entry_sort_key)
        mit_foto = [e for e in erlegungen if e.get("photo_url")]
        if mit_foto:
            state.letztes_foto_url = max(mit_foto, key=_entry_sort_key)["photo_url"]

    # Letzte Aktivität (jüngstes created_at über ALLE Einträge)
    activity_dts = [d for d in (_parse_dt(e.get("created_at")) for e in entries) if d]
    if activity_dts:
        state.letzte_aktivitaet = max(activity_dts)
        delta = datetime.now(timezone.utc) - state.letzte_aktivitaet
        state.tage_seit_aktivitaet = max(delta.days, 0)

    state.strecke_by_wildart = dict(sorted(state.strecke_by_wildart.items()))
    state.anblicke_by_wildart = dict(sorted(state.anblicke_by_wildart.items()))
    state.einrichtungen_by_type = dict(sorted(state.einrichtungen_by_type.items()))
    return state
