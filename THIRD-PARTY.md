# Zależności i modele

Licencja MIT ListenActive dotyczy jego własnego kodu. Zależności zachowują swoje licencje.

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://github.com/OpenNMT/CTranslate2), [ONNX Runtime](https://github.com/microsoft/onnxruntime): MIT.
- [Whisper](https://github.com/openai/whisper): MIT; modele pobierane na komputer użytkownika.
- [Tokenizers](https://github.com/huggingface/tokenizers), [Hugging Face Hub](https://github.com/huggingface/huggingface_hub): Apache-2.0.
- [PyAV](https://github.com/PyAV-Org/PyAV): BSD-3-Clause; jego biblioteki FFmpeg podlegają odrębnym licencjom.
- [Python](https://docs.python.org/3/license.html): PSF License; Tcl/Tk: licencje Tcl/Tk.
- [PyInstaller](https://pyinstaller.org/en/stable/license.html): GPL z wyjątkiem umożliwiającym dystrybucję spakowanych aplikacji na własnych licencjach.
- [NVIDIA cuBLAS](https://docs.nvidia.com/cuda/eula/index.html) i [cuDNN](https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html): licencje NVIDIA; dołączone biblioteki wykonawcze służą akceleracji aplikacji.
- [FFmpeg 7.1.1, build gyan.dev](https://www.gyan.dev/ffmpeg/builds/): zewnętrzny program GPLv3 pobierany bezpośrednio przez użytkownika przy pierwszym użyciu; nie jest dołączony do ZIP ListenActive. Licencja jest pobierana razem z programem. [Źródła FFmpeg](https://github.com/FFmpeg/FFmpeg/tree/n7.1.1).

Pełne informacje licencyjne dystrybuowanych pakietów są dołączane do katalogu `licenses` w wydaniu przez skrypt `collect_licenses.py`.
