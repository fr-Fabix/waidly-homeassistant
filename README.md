<p align="center">
  <img src="https://raw.githubusercontent.com/fr-Fabix/waidly-homeassistant/main/icon.png" width="120" alt="Waidly">
</p>

<h1 align="center">Waidly Online-Revier — Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/badge/version-0.1.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
</p>

Bringt dein **[Waidly](https://waidly.de) Online-Revier** als read-only-Integration
nach Home Assistant: Strecke, Anblicke, Einrichtungen (mit Zustand), Jagdkalender
und Echtzeit-**Events** für Automationen. Datenquelle ist die öffentliche
`web-revier`-API (Code-Authentifizierung) — es werden **keine Mitgliederdaten**
übernommen.

> ℹ️ **Read-only.** Erlegungen/Einrichtungen werden in der Waidly-App gepflegt;
> diese Integration spiegelt sie nur. Für Schreibrechte ist nichts erforderlich —
> ein **Lese-Code** genügt.

## Installation

### HACS (empfohlen)

1. HACS → **⋮ → Benutzerdefinierte Repositories**
2. Repository: `https://github.com/fr-Fabix/waidly-homeassistant` · Kategorie: **Integration** → Hinzufügen
3. „Waidly Online-Revier" installieren → **Home Assistant neu starten**

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fr-Fabix&repository=waidly-homeassistant&category=integration)

### Manuell

`custom_components/waidly_revier/` nach `<config>/custom_components/` kopieren und HA neu starten.

## Einrichtung

**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Waidly Online-Revier"**
→ deinen Revier-**Zugangscode** (z. B. `WDL-…`) eingeben.

In den **Optionen** lassen sich Abruf-Intervall (Standard 15 Min) und
Inaktivitäts-Schwelle (Standard 14 Tage) anpassen.

## Entities (Gerät „Revier <Name>")

| Entity | Inhalt |
|---|---|
| `sensor.…_strecke` | Stück lfd. Jagdjahr (1.4.–31.3.), Attribut `je_wildart` |
| `sensor.…_strecke_<wildart>` | Strecke je Wildart (dynamisch) |
| `sensor.…_anblicke` | Anblicke (Sichtungen) lfd. Jagdjahr |
| `sensor.…_letzte_erlegung` | „Wildart Unterart" + alle Felder als Attribute |
| `sensor.…_letzte_aktivitaet` / `…_tage_seit_aktivitaet` | Frische der Daten |
| `sensor.…_wildbret` / `…_erloes` | Σ Gewicht (kg) / Erlös (€) lfd. Jagdjahr |
| `sensor.…_einrichtungen` | Anzahl, Attribut `je_typ` |
| `sensor.…_wartung_notig` | Einrichtungen mit Zustand ≠ Gut (Liste als Attribut) |
| `sensor.…_wildkameras` | Anzahl Wildkameras |
| `sensor.einrichtung_<name>` | **State = Zustand** (Gut/Mittel/Schlecht) + alle Felder als Attribute |
| `binary_sensor.…_inaktiv` | An, wenn > Schwelle Tage kein Eintrag |
| `calendar.…_jagdkalender` | Alle Erlegungen/Anblicke auf ihrem Datum |
| `image.…_letztes_erlegungsfoto` | Foto der jüngsten Erlegung (falls vorhanden) |

## Events (für Automationen)

`waidly_neue_erlegung` · `waidly_neuer_anblick` · `waidly_einrichtung_wartung` —
jeweils mit reichem Payload (wildart, schuetze, gewicht, GPS, spot_id …). Filtern
in der Automation, z. B. nur Schwarzwild:

```yaml
triggers:
  - trigger: event
    event_type: waidly_neue_erlegung
conditions:
  - "{{ trigger.event.data.wildart == 'Schwarzwild' }}"
actions:
  - action: notify.mobile_app_xyz
    data:
      message: "🐗 Schwarzwild erlegt von {{ trigger.event.data.schuetze }}"
```

## Dashboard

Fertige Karten (Einrichtungs-Ampel nach Zustand, Überblick, Kalender) liegen in
[`dashboard/waidly-revier-cards.yaml`](dashboard/waidly-revier-cards.yaml).
Benötigt die HACS-Karten `auto-entities`, `mushroom`, `card-mod`.

## Hinweise

- **Kein Live-„funktioniert"-Signal** für Einrichtungen — Status ist das in der App
  gepflegte Feld `zustand`.
- Das Integrations-**Logo** in der HA-Oberfläche stammt aus dem
  [home-assistant/brands](https://github.com/home-assistant/brands)-Repo (separater
  PR, siehe `brands/` in diesem Repo).
- Inoffizielle Community-Integration. Kein offizieller Support durch Waidly.

## Lizenz

[MIT](LICENSE) © 2026 Fabian Ripp (RIPPCON)
