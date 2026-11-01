# moode-charlcd – Plan und Stand

Ziel: Das 20x4-Zeichendisplay (Joy-IT RB-LCD-20x4, HD44780 über PCF8574 an I2C 0x27) und die
Taster am Raspberry Pi unter moOde mindestens so nutzen wie früher mit `mopidy-charlcd` +
`mopidy-raspberry-gpio`, zusätzlich Infos anderer moOde-Renderer anzeigen.

**Stand 2026-11-01:** v0.2.1 ist auf dem Pi installiert, die Prüfung am Gerät läuft
(siehe „Am Pi prüfen“).

| Repo | Branch | Commit |
|---|---|---|
| `moode-charlcd` | `rewrite-moode` | Rewrite as standalone moOde daemon |
| `nc-server-provisioning` | `add-moode-charlcd` (von `moodeaudio`) | Add install script for moode-charlcd display service |

Beide Branches sind nur lokal (nicht gepusht).

---

## 1. Entscheidungen

- **Eigener Daemon** statt moOde „LCD updater“ (Prozess pro Update, keine Laufzeit/Uhr),
  LCDproc/mpdlcd (nur MPD) oder pydPiper (unmaintained).
- **Display-HAL auf Zeichenraster-Ebene** (`CharacterDisplay`): Andere Zeichendisplays brauchen
  nur einen Treiber + Eintrag in `hal/factory.py`. Grafikdisplays sind nicht vorgesehen.
- **Eingangsseite über Adapter** (`PlayerAdapter`) mit Repositories/Clients dahinter
  (MPD-Protokoll, moOde-SQLite, Metadaten-JSON, BlueZ über `busctl`).
- **Renderer-Erkennung über moOdes Datenbank** (`cfg_system.*active`, read-only) und die
  Metadatendateien (`spotmeta.json`, `aplmeta.json`, …) statt `currentsong.txt`. Vorteil: Die
  moOde-Option „Metadata file“ muss nicht aktiviert werden, Erkennung im Sekundentakt.
- **Bluetooth direkt über BlueZ** (`org.bluez.MediaPlayer1`): Titel, Spielzeit und Steuerung
  (Play/Pause/Vor/Zurück). `btmeta.json` gibt es erst in neuen moOde-Versionen.
- **AirPlay** wird nur angezeigt, keine Tastensteuerung (wird nicht genutzt). Spotify: nur Anzeige.
- **Eigener HD44780/PCF8574-Treiber auf `smbus2`** statt `I2C-HD77480-LCD` + Adafruit Blinka.
  Das Joy-IT-Board braucht die nicht standardkonforme Pinbelegung „joyit“
  (D4–D7 = P0–P3, RS = P4, EN = P7, kein Backlight-Bit); „standard“ ist ebenfalls eingebaut.
- **Konsolenausgabe** bleibt als Feature: `--display console` (ohne Hardware) oder
  `--console` / `console_mirror = true` (zusätzlich zum LCD, sichtbar im Journal).
- **Verteilung:** kein PyPI; Installation per `pip install "git+…@vX.Y.Z"` aus einem Git-Tag.
- **Qualität:** `ruff` (Lint + Format), `mypy --strict`, `pytest` mit Coverage, GitHub-Actions-CI.
- **Lange Tastendrücke** erst in einer späteren Ausbaustufe.

## 2. Architektur

```
sources/ (Eingang)                 service.py              ui/                    hal/
MpdAdapter (idle-Events) ──┐                               StandardLayout         Hd44780 + Pcf8574Bus
MoodeRendererAdapter ──────┼─> NowPlaying ─> NowPlayingService ─> Frame ─> Screen ─> ConsoleDisplay
  MoodeDatabase (SQLite)   │                      ▲
  MetadataFiles (JSON)     │                      │
  BluezClient (busctl)     │            buttons.py (gpiozero)
                           └─ nach Priorität, erster aktiver Adapter gewinnt
```

- `model.py`: `NowPlaying` (quellenunabhängig, inkl. unterstützter Tastenaktionen),
  Zeit-Interpolation über `elapsed_at()`.
- `ui/layout.py`: Layout wie bei mopidy-charlcd (Tastenlegende, ∞/Random/Consume, Spielzeit,
  Titel/Interpret/Album, Uhr), skaliert auf kleinere Displays (z. B. 16x2).
- `ui/screen.py`: Symbole → eingebaute Zeichen (∞ = 0xF3 im ROM A00), CGRAM-Slots (mit
  Nachprogrammierung) oder ASCII-Ersatz; überträgt nur geänderte Zeichen.
- `hal/charsets.py`: ROM A00/A02, Umlaute (ä ö ü ß, Ä → ä), Ersatzzeichen, immer 1 Code pro Zeichen.

## 3. Erledigt

- [x] Repo aufgeräumt (Mopidy-Reste, `jproperties`, `chatgpt.patch`, PyPI-Release-Workflow entfernt)
- [x] `pyproject.toml`, Entry Point `moode-charlcd`, TOML-Konfiguration mit Defaults im Paket
- [x] Display-HAL, HD44780-Treiber, PCF8574-Bus (joyit/standard), Konsolen-Display
- [x] Layout, Screen mit Diff und Slot-Verwaltung
- [x] MPD-Adapter (idle, Reconnect, Radio mit „Interpret - Titel“-Aufteilung, Optionen)
- [x] moOde-Renderer-Adapter (Spotify, AirPlay, Qobuz, Squeezelite, Roon, Plexamp, Eingang, Multiroom)
- [x] Bluetooth über BlueZ inkl. Steuerung
- [x] Taster über gpiozero (Auslösung beim Drücken; Fehler beim Einrichten → Betrieb ohne Taster)
- [x] Abschiedstext bei SIGTERM
- [x] 118 Unit-Tests ohne Hardware, Coverage ~96 %, ruff + mypy strict ohne Befunde
- [x] Probelauf lokal mit `--display console` (MPD offline, Abschiedstext)
- [x] README.md und CHANGELOG.md (Englisch), CI mit getrennten Jobs für Lint/Typprüfung und Tests (Python 3.11 und 3.13, Coverage-Zusammenfassung, Testergebnisse als Artefakt)
- [x] Provisionierung: `scripts/23-install-moode-charlcd.sh` (apt-Pakete, I2C, venv, Konfiguration,
      systemd-Dienst mit DynamicUser) und `scripts/24-config-shutdown-button.sh`
      (`dtoverlay=gpio-shutdown,gpio_pin=9,active_low=1,gpio_pull=up`, idempotent, ersetzt eine
      vorhandene `gpio-shutdown`-Zeile); `config.txt`-Bearbeitung gegen moOdes Vorlage getestet,
      ShellCheck sauber

## 4. Nächste Schritte

### Veröffentlichen (vor der Installation nötig)

- [x] Branches reviewen, `rewrite-moode` nach `master` mergen, pushen
- [x] Tag `v0.2.0` setzen und pushen (das Installationsskript installiert genau diesen Tag;
      0.2.0 statt 0.1.0, weil es aus dem früheren Code schon den Tag `0.1.1` gibt)
- [x] `add-moode-charlcd` nach `moodeaudio` mergen und pushen
- [x] CI-Lauf auf GitHub prüfen (Workflow ist aktiv, bisher aber 0 Läufe: Settings → Actions →
      „Allow all actions“, dann unter Actions „Run workflow“)

### Am Pi prüfen (blind getroffene Annahmen)

- [x] MPD-Anbindung: Mit python-mpd2 3.x (Trixie) fehlten `send_idle`/`fetch_idle`, Anzeige
      dauerhaft „MPD offline“ → behoben in v0.2.1 (blockierendes `idle()`, Test gegen echtes
      python-mpd2)
- [ ] `sudo bash scripts/23-install-moode-charlcd.sh`, Neustart, `journalctl -u moode-charlcd -f`
- [ ] `i2cdetect -y 1` zeigt 0x27; Display initialisiert mit Pinbelegung `joyit`
- [ ] Umlaute korrekt (ROM A00 vermutet; sonst `charset = "A02"`)
- [ ] Taster BCM4/16/10 lösen beim Drücken aus (Pull-up, nach GND); kein doppeltes Auslösen
      → moOde „GPIO buttons“ müssen aus sein
- [ ] lgpio funktioniert mit DynamicUser (`LG_WD=/run/moode-charlcd`)
- [ ] moOde-Datenbank für den Dienstbenutzer lesbar (Skript warnt sonst)
- [ ] Spotify: `spotactive` und `spotmeta.json` werden erkannt
- [ ] Bluetooth: `btactive` gesetzt, `busctl` liefert JSON im erwarteten Format
      (`busctl --json=short call org.bluez / org.freedesktop.DBus.ObjectManager GetManagedObjects`),
      Gruppe `bluetooth` darf mit BlueZ sprechen, `Position` läuft mit
- [ ] Shutdown-Taster BCM9 (Skript 24) → „Und tschüss!“ und Pi fährt herunter
- [ ] MPD-Neustart über die moOde-UI → Dienst verbindet sich neu
- [ ] Radio: Sender + Stream-Titel
- [ ] Bei Abweichungen Testdaten (z. B. echte `busctl`-Ausgabe, `*meta.json`) in `tests/` übernehmen

### Phase 8 – Abschluss

- [ ] Wenn die Abnahme am Gerät erfolgreich war: **`mopidy-charlcd` archivieren** (README-Hinweis auf
      `moode-charlcd`, GitHub-Repo auf „archived“ setzen, ggf. PyPI-Projekt als veraltet markieren).

## 5. Spätere Ausbaustufen

- [ ] Lange Tastendrücke, z. B. next lang = Random umschalten, play lang = Stop,
      im Renderer-Modus play lang = Renderer trennen (moOde-Funktion „Disconnect“).
- [ ] Weitere Tastenfunktionen (Lautstärke, Playlist/Radiosender wählen).
- [ ] Laufschrift für zu lange Titel (derzeit abgeschnitten).
- [ ] Leerlaufanzeige (z. B. Hostname/IP bei gestopptem MPD).
- [ ] Hintergrundbeleuchtung zeitgesteuert abschalten (nur bei Pinbelegung mit Backlight-Bit).
