ListenActive 0.1.1 na Windows 10 i 11 (64-bit).

Poprawiono zakończenie uploadu: klient wysyła prawidłowy JSON do API. Test z działającym Dockerem potwierdził przesyłanie i wznawianie, odtwarzanie 360p/480p/720p/1080p, miniaturę, transkrypcję oraz unieważnianie zadań.

- Tryb samodzielny: lokalna transkrypcja nagrania do SRT i TXT.
- Tryb strony: wszystkie jakości HLS, okładka i opcjonalna transkrypcja powstają na komputerze redaktora; wysyłane są gotowe pliki.
- NVIDIA NVENC/CUDA oraz automatyczny tryb CPU. Domyślny model large-v3.
- Wznawianie przerwanego wysyłania i wykorzystanie ukończonych jakości po ponownym uruchomieniu.

Rozpakuj cały ZIP i uruchom ListenActive.exe. Pierwsze użycie pobiera FFmpeg i wybrany model. Zależności Python i biblioteki wykonawcze GPU są w paczce. Kod aplikacji jest na licencji MIT; zależności mają własne licencje.

Sprawdzono lokalne kodowanie i transkrypcję na RTX 4070 Ti oraz CPU. Integracja strony wymaga backendu protokołu 1 opisanego w INTEGRATION.md. Test integracji z Dockerem zakończył się powodzeniem. Aplikacja nie ma podpisu Authenticode.
