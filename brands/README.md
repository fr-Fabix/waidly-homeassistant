# Brand-Assets für home-assistant/brands

Damit das Waidly-Logo in der Home-Assistant-Oberfläche erscheint, müssen diese
Dateien per PR ins offizielle Repo [home-assistant/brands](https://github.com/home-assistant/brands):

```
custom_integrations/waidly_revier/icon.png   (256×256)
custom_integrations/waidly_revier/logo.png
```

Vorgehen: Repo forken, Ordner `custom_integrations/waidly_revier/` mit diesen
beiden PNGs anlegen, PR öffnen. Bis zum Merge zeigt HA ein generisches Icon —
die Integration funktioniert trotzdem voll.
