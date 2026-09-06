# Integracja ze stroną — protokół 1

Serwer nie potrzebuje FFmpeg, Pythona, CUDA ani modelu mowy. Wymagane są HTTPS, baza danych dla autoryzacji i sesji przesyłania oraz magazyn gotowych plików. Ten sam protokół działa z usługami w Dockerze lub uruchomionymi bezpośrednio w maszynie Linux na Proxmox.

## Przekazanie zadania

Zalogowany redaktor pobiera z panelu lekcji JSON:

```json
{
  "protocol": 1,
  "apiUrl": "https://kursy.example/api/v1",
  "jobId": "11111111-1111-4111-8111-111111111111",
  "token": "<43 znaki base64url, 32 losowe bajty>",
  "kind": "video",
  "title": "Tytuł lekcji",
  "expiresAt": "2026-09-13T12:00:00Z"
}
```

`kind` przyjmuje `video` (pełny film) lub `transcript` (sam tekst dla istniejącego filmu). Token jest ograniczony do jednego zadania, jednej lekcji i wersji filmu. Serwer przechowuje tylko SHA-256 tokenu, ponownie sprawdza aktywność konta, sesji oraz aktualne uprawnienia przy każdym żądaniu. Unieważnienie zadania lub sesji blokuje przesyłanie. Aplikacja nie przekazuje tokenu do logów, parametrów URL ani kolejnego hosta przez przekierowanie.

Endpoint panelu: `POST /desktop-media/videos/:videoId/jobs` z `{ "kind": "video" }`, uwierzytelnienie sesją i CSRF. `DELETE` pod tym adresem unieważnia aktywne zadania filmu.

## Wywołania aplikacji Windows

Wszystkie poniższe ścieżki względem `apiUrl`, nagłówek `Authorization: Bearer <token>`:

| Metoda | Ścieżka | Znaczenie |
| --- | --- | --- |
| GET | `/desktop-media/jobs/:id` | `completed`, `stale`, lista `uploaded` |
| POST | `/desktop-media/jobs/:id/manifest` | niezmienny opis przygotowanej paczki |
| PUT | `/desktop-media/jobs/:id/files/:path` | gotowy plik, `application/octet-stream`; path zakodowany jako pojedynczy segment URL |
| POST | `/desktop-media/jobs/:id/complete` | atomowe przypisanie kompletnych materiałów |
| POST | `/desktop-media/jobs/:id/transcript` | gotowa transkrypcja dla zadania rodzaju `transcript` |

Limit pliku: 24 MiB. Limit JSON manifestu/transkrypcji: 8 MiB. Maksymalnie 50 000 plików, 24 godziny, 6 jakości. Suma bajtów paczki podlega limitowi platformy. Odpowiedzi 401/403 oznaczają brak dostępu, 409 konflikt wersji/paczki, 400 nieprawidłowe dane. Błędy sieciowe, 429 oraz przejściowe 5xx można ponawiać z opóźnieniem. Po 409 należy pobrać nowe zadanie; lokalne wyniki pozostają.

## Manifest

Dokładny format i generowanie kanonicznych playlist znajdują się w `engine.py`: `Engine.prepare()` oraz `playlist()`. Główne pola:

- `protocol: 1`, `sourceSha256`, `duration`, `width`, `height`;
- `renditions[]`: `label`, `width`, `height`, `bitrate`, `audioBitrate`, `durations[]`;
- `files[]`: `path`, `size`, `sha256`;
- opcjonalnie `transcript`: `sourceSha256`, `model`, `language`, `segments[]` (`start`, `end`, `text`).

Ścieżki: `master.m3u8`, `poster.jpg`, `<wysokość>p/index.m3u8`, `<wysokość>p/segment_000000.ts` itd. Każdy plik musi mieć poprawną długość i SHA-256; serwer porównuje playlisty z kanoniczną treścią i sprawdza nagłówki TS/JPEG. Nie uruchamia dekodera ani renderera. Żaden oryginalny MP4/MKV/MOV/WebM nie jest przesyłany. Finalizacja przyjmuje tylko pełny komplet zadeklarowanych plików.

Idempotentne PUT przesyła dokładnie te same bajty. GET zwraca pliki zapisane i potwierdzone przez serwer; klient pomija je przy wznowieniu. Finalizacja jest idempotentna i sprawdza wersję filmu, dzięki czemu starsze zadanie nie nadpisze nowej zmiany redaktora. Materiały są prywatne i odtwarzane przez istniejącą kontrolę dostępu strony. Każda wersja ma odrębne ścieżki, aby pamięć podręczna nie pomieszała segmentów.

Przy ponownej transkrypcji serwer sprawdza hash oryginału. Ręczne poprawki są chronione; ich zastąpienie wymaga importu SRT z podglądem w panelu. Publikacja strony/kursu pozostaje czynnością panelu; aplikacja podmienia tylko materiał przypisanej lekcji.
