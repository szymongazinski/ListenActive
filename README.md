# ListenActive

Aplikacja Windows 10/11 x64 do lokalnej transkrypcji oraz przygotowania filmów dla platformy kursowej. Nagranie źródłowe pozostaje na komputerze redaktora.

## Pobieranie

Pobierz `ListenActive-Windows-x64.zip` z [wydań](https://github.com/szymongazinski/ListenActive/releases), rozpakuj cały katalog i uruchom `ListenActive.exe`. Python nie jest wymagany. Aplikacja nie ma jeszcze podpisu Authenticode.

Pierwsze użycie pobiera FFmpeg (około 104 MB, sprawdzana przypięta suma SHA-256) oraz wybrany model mowy (dla large-v3 kilka GB). Kolejne transkrypcje nie wymagają wysyłania nagrania ani połączenia ze stroną. Modele i narzędzia są przechowywane w `%LOCALAPPDATA%\ListenActive`.

## Dwa tryby

1. **Transkrypcja do SRT i TXT:** wybierz nagranie audio/wideo oraz folder wyników. Aplikacja zapisuje pliki UTF-8 `transcript.srt`, `transcript.txt` i `transcript.json`. Konto na stronie nie jest potrzebne.
2. **Pełna obsługa strony:** pobierz plik zadania `.redaktor.json` w edytorze lekcji, otwórz go w aplikacji, wybierz film i folder wyników. Aplikacja lokalnie generuje transkrypcję (można wyłączyć), okładkę JPEG i wszystkie jakości HLS do rozdzielczości źródła, maksymalnie 1440p, a następnie wysyła tylko gotowe pliki. Zadanie samej transkrypcji przesyła wyłącznie tekst.

Domyślne jakości: 360p, 480p, 720p, 1080p, 1440p; aplikacja nie powiększa źródła. Wideo H.264, audio AAC, segmenty MPEG-TS po około 6 sekund. Każda jakość obejmuje całe nagranie. Brak automatycznego przełączania na mniej dokładny model.

## GPU i słabsze komputery

NVIDIA: NVENC do kodowania, NVDEC/CUDA do zgodnego dekodowania i skalowania oraz CUDA do rozpoznawania mowy. RTX 4070 Ti 12 GB, Ryzen 7 5800X i 32 GB RAM są docelowym zestawem. Biblioteki CUDA/cuDNN są dołączone do wydania, wymagany jest kompatybilny sterownik NVIDIA. Gdy GPU nie jest dostępne lub nie obsługuje pliku, aplikacja korzysta z CPU. AMD/Intel działają w trybie CPU.

CPU używa modelu int8 i ograniczonej liczby wątków. Na słabszym komputerze przygotowanie nagrania może potrwać znacznie dłużej; można ręcznie wybrać model `small` lub `large-v3-turbo`. Najdokładniejszy `large-v3` jest domyślny. Jakości powstają kolejno, a transkrypcja i kodowanie nie konkurują jednocześnie o pamięć GPU.

## Wznawianie i przechowywanie

Wybierz ponownie ten sam plik i folder wyników. Ukończone jakości oraz transkrypcja są wykorzystywane ponownie. Po przerwaniu kodowania ponawiana jest tylko niedokończona jakość. Wysyłanie wznawia się od nieprzesłanych segmentów, także po ponownym uruchomieniu programu. Zachowaj oryginalny film do przyszłego generowania transkrypcji.

Zadania strony wygasają po 7 dniach; wylogowanie/unieważnienie sesji lub odebranie uprawnień blokuje dalsze przesyłanie. Po wygaśnięciu pobierz nowe zadanie i użyj zachowanych wyników. Nie udostępniaj pliku zadania — zawiera uprawnienie do wysłania materiału dla jednej lekcji. Wysłanie nowego filmu zastępuje jego transkrypcję; ręczne poprawki przy ponownej transkrypcji tego samego filmu są chronione, w takim przypadku użyj importu SRT z podglądem na stronie.

## Uruchomienie ze źródeł

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python main.py
```

## Budowanie wydania

```powershell
.venv/Scripts/python -m unittest discover -s tests
.venv/Scripts/python -m PyInstaller --noconfirm ListenActive.spec
Compress-Archive -Path dist/ListenActive -DestinationPath dist/ListenActive-Windows-x64.zip
```

Kod aplikacji jest na licencji MIT. Zależności i modele mają własne licencje opisane w [THIRD-PARTY.md](THIRD-PARTY.md). Protokół strony: [INTEGRATION.md](INTEGRATION.md).
