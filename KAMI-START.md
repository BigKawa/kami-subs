# Kami Subs starten

## Ohne Befehle einzugeben

Im Ordner `C:\Users\Nutzer\GitHub\kami-subs` die Datei `Kami-starten.bat` doppelt anklicken. Sie startet den Server mit der Python-Umgebung aus `backend\.venv`. Das Terminalfenster bleibt für den Server geöffnet. Danach im Videotab die Kami-Erweiterung öffnen und Start anklicken.

Nur einmal starten. Zum Beenden im Serverfenster Strg+C drücken.

## Start in der Eingabeaufforderung (cmd)

```cmd
cd /d C:\Users\Nutzer\GitHub\kami-subs\backend
call .venv\Scripts\activate.bat
.venv\Scripts\python.exe server.py
```

## Start in PowerShell

```powershell
Set-Location 'C:\Users\Nutzer\GitHub\kami-subs\backend'
& '.\.venv\Scripts\python.exe' server.py
```

Eine Aktivierung ist bei diesem direkten Aufruf nicht erforderlich.

## Welche BAT-Datei macht was?

- `backend\.venv\Scripts\activate.bat`: Aktiviert die Backend-Umgebung in cmd, startet aber keinen Server.
- `Kami-starten.bat`: Startet den Server per Doppelklick.
- `extension\native\launcher.bat`: Wird von der Browser-Erweiterung aufgerufen, wenn der Native-Messaging-Host eingerichtet ist. Nicht direkt doppelt anklicken. Die Funktion in deiner aktuellen Brave-Installation wurde für diese Anleitung nicht geprüft.

Verwende die Umgebung unter `backend\.venv`, nicht die separate `.venv` im Hauptordner. Bei unserer Prüfung am 27.09.2026 enthielt nur die Backend-Umgebung die benötigten Pakete.

## Nach Änderungen an der Erweiterung

1. In Brave `brave://extensions` öffnen.
2. Bei Kami Subs auf Neu laden klicken.
3. Den Videotab neu laden.
4. Kami öffnen und Start anklicken.

Ein reiner Overlay-Fix erfordert das Neuladen der Erweiterung und des Videotabs; ein Serverneustart allein übernimmt ihn nicht.

## Server normal stoppen

1. In der Kami-Erweiterung **Stop** anklicken, damit die Audioaufnahme endet.
2. Wenn du den Server selbst mit `Kami-starten.bat` oder im Terminal gestartet hast: ins Serverfenster klicken und **Strg+C** drücken (Tastenkombination, kein einzutippender Befehl).
3. Auf `Application shutdown complete` / `Finished server process` warten. Danach ist der Server beendet. Falls cmd fragt, ob der Batchvorgang beendet werden soll, mit `J` bestätigen.

`client disconnected` allein bedeutet nur, dass die Browserverbindung getrennt wurde; der Server kann weiterlaufen. Ein von der Erweiterung selbst gestarteter Server wird über deren Stop-Funktion beendet. Ein manuell gestarteter Server muss separat gestoppt werden.

## Wenn der Server hängt: gezielt erzwingen

Zuerst Strg+C versuchen. Wenn das Serverfenster nicht mehr erreichbar ist oder der Prozess hängen bleibt, ein neues Terminal öffnen.

### 1. Server-PID über den Port finden (cmd oder PowerShell)

Der Standardport im aktuellen Code ist **8765**. Falls du `KAMI_PORT` geändert hast, den geänderten Port verwenden.

```cmd
netstat -ano | findstr :8765
```

Die Zeile mit der lokalen Adresse `127.0.0.1:8765` (bzw. einer anderen lokalen Bindeadresse) und Status `LISTENING` / `ABHÖREN` suchen. Die letzte Zahl ist die Prozess-ID (PID). Nicht die PID einer beliebigen Client-Verbindung verwenden.

### 2. Prozess vor dem Beenden prüfen (PowerShell)

Im folgenden Beispiel ist **12345 ein Platzhalter**. Durch die gerade ermittelte PID ersetzen:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = 12345" | Select-Object ProcessId, ExecutablePath, CommandLine
```

Nur fortfahren, wenn der Prozess zum Kami-Backend gehört (Python aus `kami-subs\backend\.venv` und Aufruf von `server.py`). Wenn es ein anderer Dienst ist oder die Zuordnung unklar bleibt, nicht beenden.

### 3. Genau diesen Prozess beenden (cmd oder PowerShell)

Auch hier **12345 durch die geprüfte PID ersetzen**:

```cmd
taskkill /PID 12345 /F
```

Anschließend erneut prüfen:

```cmd
netstat -ano | findstr :8765
```

Es sollte keine lauschende Serverzeile mehr geben. Verbindungen mit `TIME_WAIT` können noch kurz sichtbar sein. Kein pauschales `taskkill /IM python.exe /F` verwenden: Das würde auch andere Python-Projekte beenden.

Diese Kill-Befehle sind eine ergänzte Notfall-Anleitung, kein Nachweis dafür, dass wir sie früher ausgeführt haben.

## Sauber neu starten

1. Kami im Browser stoppen.
2. Server wie oben beenden und das Ende abwarten.
3. `Kami-starten.bat` im Repo doppelt anklicken, alternativ die Startbefehle oben nutzen.
4. Auf die Startmeldung `Uvicorn running on ...` warten. Beim ersten Laden des Modells kann das etwas dauern.
5. Im Videotab Kami öffnen und **Start** anklicken.

Bei Änderungen an `server.py` oder `config.py` den Server neu starten. Bei Änderungen am Extension-/Overlay-Code zusätzlich die Erweiterung unter `brave://extensions` und anschließend den Videotab neu laden.

## Häufige Probleme aus unserer bisherigen Arbeit

### `ModuleNotFoundError: No module named 'numpy'`

Bei uns war die falsche virtuelle Umgebung ausgewählt. Auch wenn im Prompt `(.venv)` steht, kann es die Umgebung im Hauptordner sein. Direkt die richtige Python-Datei aufrufen:

```cmd
cd /d C:\Users\Nutzer\GitHub\kami-subs\backend
.venv\Scripts\python.exe server.py
```

Zum Prüfen der Umgebung, ohne den Server zu starten (cmd oder PowerShell, aus dem Backend-Ordner):

```cmd
.venv\Scripts\python.exe -c "import sys, numpy, faster_whisper; print(sys.executable); print('Pakete vorhanden')"
```

### `can't open file` / vertippter Startbefehl

Die Eingabezeile leeren und den vollständigen Startbefehl erneut einfügen. `activate.bat` nicht an `python server.py` anhängen. Die Datei heißt exakt `server.py`.

### Port belegt / `WinError 10048` / `address already in use`

Es läuft möglicherweise bereits ein Server. Nicht noch weitere Instanzen starten. Mit der Port-/PID-Prüfung oben feststellen, welcher Prozess den Port verwendet; nur den eindeutig zugeordneten Kami-Prozess stoppen und anschließend einmal neu starten.

### Server übersetzt, aber Untertitel fehlen

Ausgaben wie `pending=...` und `out=...` belegen die Verarbeitung im Backend, nicht die sichtbare Anzeige im Browser. Verbindung und Start-Status im Kami-Popup prüfen. Nach Overlay-Änderungen Erweiterung und Videotab neu laden.

Getrennt prüfen: normales Video, Player-/Video-Vollbild, Brave-F11 und Vergrößern/Resize. Beim bisherigen Fix wurden die automatisierten Brave-Szenarien bestanden; echtes F11 blieb wegen der abgebrochenen UI-Steuerung unbestätigt.

### `hallucination filter dropped` / Vocalization-Filter

Das ist eine Filtermeldung, kein Serverabsturz. Beispielsweise wurde `ご視聴ありがとうございました` als typische Whisper-Halluzination unterdrückt. Nicht allein wegen dieser Meldung neu starten oder Filter deaktivieren.

## Python-Umgebung verlassen

Nach dem Stoppen des Servers kannst du in einem zuvor aktivierten cmd-Terminal eingeben:

```cmd
deactivate
```

Das verlässt nur die virtuelle Umgebung; es beendet keinen laufenden Server.
