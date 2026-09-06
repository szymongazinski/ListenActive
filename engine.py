"""ListenActive's local processing engine. Never sends a source recording to a server."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

VERSION = '0.1.0'
APP_DATA = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ListenActive'
FFMPEG_URL = 'https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip'
FFMPEG_SHA256 = '04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4'
LADDER = [(360, 800000, 96000), (480, 1400000, 112000), (720, 2500000, 128000),
          (1080, 5000000, 160000), (1440, 8000000, 192000)]
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class Cancelled(Exception):
    pass


def digest(path: Path, cancel=None):
    result = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            if cancel and cancel.is_set():
                raise Cancelled()
            result.update(chunk)
    return result.hexdigest()


def atomic_json(path: Path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def validate_job(value):
    if not isinstance(value, dict) or value.get('protocol') != 1:
        raise ValueError('Nieobsługiwana wersja zadania.')
    parsed = urllib.parse.urlsplit(value.get('apiUrl', ''))
    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
    if (parsed.scheme != 'https' and not (parsed.scheme == 'http' and local)) or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('Adres strony musi używać HTTPS (HTTP dozwolony tylko dla localhost).')
    if parsed.path.rstrip('/') != '/api/v1':
        raise ValueError('Nieprawidłowy adres API.')
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', value.get('jobId', '')) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value.get('token', '')):
        raise ValueError('Nieprawidłowy plik zadania.')
    if value.get('kind') not in ('video', 'transcript'):
        raise ValueError('Nieobsługiwany rodzaj zadania.')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Serwer próbował przekierować przesyłanie. Pobierz aktualne zadanie ze strony.')


class SiteClient:
    def __init__(self, job, cancel, report):
        self.job = validate_job(job)
        self.cancel = cancel
        self.report = report
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, method, path='', data=None, binary=False):
        url = self.job['apiUrl'].rstrip('/') + '/desktop-media/jobs/' + self.job['jobId'] + path
        payload = data if binary else (json.dumps(data).encode() if data is not None else None)
        for attempt in range(6):
            if self.cancel.is_set():
                raise Cancelled()
            req = urllib.request.Request(url, data=payload, method=method, headers={
                'Authorization': 'Bearer ' + self.job['token'],
                'Content-Type': 'application/octet-stream' if binary else 'application/json',
                'User-Agent': 'ListenActive/' + VERSION,
            })
            try:
                with self.opener.open(req, timeout=90) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code not in (408, 429, 500, 502, 503, 504):
                    try:
                        body = json.loads(exc.read(16384))
                        message = body.get('message', f'Błąd serwera: {exc.code}')
                    except (ValueError, AttributeError):
                        message = f'Błąd serwera: {exc.code}'
                    raise RuntimeError(str(message)) from None
                delay = min(60, max(2 ** attempt, int(exc.headers.get('Retry-After', '0')) if exc.headers.get('Retry-After', '').isdigit() else 0))
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                delay = min(30, 2 ** attempt)
            if attempt == 5:
                raise RuntimeError('Połączenie przerwane. Gotowe pliki zachowano. Kliknij ponownie, aby wznowić wysyłanie.')
            self.report(f'Ponawianie połączenia za {delay} s…')
            if self.cancel.wait(delay):
                raise Cancelled()

    def upload(self, folder, manifest):
        state = self.request('GET')
        if state['completed']:
            self.report('To zadanie zostało już przesłane.')
            return
        if state['stale']:
            raise RuntimeError('Film zmienił się na stronie. Pobierz nowe zadanie i wybierz ten sam plik oraz folder wyników.')
        self.request('POST', '/manifest', manifest)
        uploaded = set(state['uploaded'])
        total = sum(item['size'] for item in manifest['files'])
        done = sum(item['size'] for item in manifest['files'] if item['path'] in uploaded)
        for item in manifest['files']:
            if item['path'] in uploaded:
                continue
            path = folder / item['path']
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != item['sha256']:
                raise RuntimeError('Gotowy plik zmienił się na dysku. Użyj nowego folderu wyników.')
            self.report(f'Wysyłanie {done / total:.0%}: {item["path"]}')
            self.request('PUT', '/files/' + urllib.parse.quote(item['path'], safe=''), content, binary=True)
            done += item['size']
        self.report('Wszystkie pliki przesłane. Sprawdzanie kompletności na stronie…')
        self.request('POST', '/complete')


def renditions(width, height, has_audio):
    rows = [entry for entry in LADDER if entry[0] <= height]
    if not rows:
        rows = [(height // 2 * 2, 500000, 64000)]
    return [dict(label=f'{h}p', height=h, width=max(2, min(width // 2 * 2, round(width * h / height / 2) * 2)),
                 bitrate=rate, audioBitrate=audio if has_audio else 0) for h, rate, audio in rows]


def playlist(manifest, path):
    if path == 'master.m3u8':
        return '#EXTM3U\n#EXT-X-VERSION:3\n' + ''.join(
            f'#EXT-X-STREAM-INF:BANDWIDTH={math.ceil((r["bitrate"] + r["audioBitrate"]) * 1.2)},RESOLUTION={r["width"]}x{r["height"]}\n{r["label"]}/index.m3u8\n'
            for r in manifest['renditions'])
    row = next(r for r in manifest['renditions'] if path == r['label'] + '/index.m3u8')
    return f'#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:{math.ceil(max(row["durations"]))}\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-INDEPENDENT-SEGMENTS\n' + ''.join(
        f'#EXTINF:{duration:.6f},\nsegment_{index:06d}.ts\n' for index, duration in enumerate(row['durations'])) + '#EXT-X-ENDLIST\n'


def srt_time(seconds):
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'


def export_transcript(folder, transcript):
    atomic_json(folder / 'transcript.json', transcript)
    (folder / 'transcript.txt').write_text('\n\n'.join(s['text'] for s in transcript['segments']) + '\n', encoding='utf-8')
    (folder / 'transcript.srt').write_text(''.join(
        f'{i + 1}\n{srt_time(s["start"])} --> {srt_time(s["end"])}\n{s["text"]}\n\n'
        for i, s in enumerate(transcript['segments'])), encoding='utf-8')


class Engine:
    def __init__(self, report, cancel):
        self.report = report
        self.cancel = cancel
        self.ffmpeg = None
        self.ffprobe = None

    def run(self, args, duration=None):
        """Drain output in a reader thread so stop works even during quiet model loading."""
        import queue
        lines = queue.Queue()
        process = subprocess.Popen([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace', creationflags=CREATE_NO_WINDOW)
        def drain():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)
        threading.Thread(target=drain, daemon=True).start()
        output = []
        last_report = 0
        try:
            while True:
                if self.cancel.is_set():
                    process.terminate()
                    raise Cancelled()
                try:
                    line = lines.get(timeout=0.2)
                except queue.Empty:
                    continue
                if line is None:
                    break
                output.append(line)
                if len(output) > 10000:
                    output = output[-5000:]
                if duration and line.startswith('out_time_us=') and time.monotonic() - last_report > 1:
                    try:
                        self.report(f'Kodowanie: {min(100, int(line.split("=")[1]) / 1000000 / duration * 100):.0f}%')
                        last_report = time.monotonic()
                    except ValueError:
                        pass
                elif line.startswith('LISTENACTIVE:'):
                    self.report(line.split(':', 1)[1].strip())
            code = process.wait()
            text = ''.join(output)
            if code != 0:
                raise RuntimeError(f'Proces zakończony błędem {code}:\n{text[-3000:]}')
            return text
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()

    def ensure_tools(self):
        folder = APP_DATA / 'tools' / 'ffmpeg-7.1.1'
        self.ffmpeg, self.ffprobe = folder / 'ffmpeg.exe', folder / 'ffprobe.exe'
        if self.ffmpeg.exists() and self.ffprobe.exists():
            return
        self.report('Pierwsze uruchomienie: pobieranie FFmpeg (około 104 MB)…')
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / 'download.zip'
        with urllib.request.urlopen(FFMPEG_URL, timeout=60) as response, archive.open('wb') as target:
            while chunk := response.read(1024 * 1024):
                if self.cancel.is_set():
                    raise Cancelled()
                target.write(chunk)
        if digest(archive, self.cancel) != FFMPEG_SHA256:
            archive.unlink(missing_ok=True)
            raise RuntimeError('Nieprawidłowa suma kontrolna FFmpeg. Spróbuj ponownie później.')
        with zipfile.ZipFile(archive) as package:
            for filename in ('ffmpeg.exe', 'ffprobe.exe', 'LICENSE'):
                entry = next(name for name in package.namelist() if name.endswith('/' + filename))
                with package.open(entry) as source, (folder / (filename + '.tmp')).open('wb') as output:
                    shutil.copyfileobj(source, output)
                (folder / (filename + '.tmp')).replace(folder / filename)
        archive.unlink()

    def prepare(self, source, destination, video=True, transcribe=True, device='auto', model='large-v3', language='pl'):
        source, destination = Path(source).resolve(), Path(destination).resolve()
        if not source.is_file():
            raise ValueError('Wybierz istniejący plik nagrania.')
        self.ensure_tools()
        self.report('Sprawdzanie pliku i obliczanie sumy kontrolnej…')
        fingerprint = digest(source, self.cancel)
        folder = destination / ('ListenActive-' + fingerprint[:16])
        folder.mkdir(parents=True, exist_ok=True)
        probe = json.loads(self.run([self.ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', source]))
        duration = float(probe['format']['duration'])
        if not math.isfinite(duration) or not 0 < duration <= 86400:
            raise ValueError('Nagranie musi mieć długość od 0 do 24 godzin.')
        streams = probe.get('streams', [])
        has_audio = any(s['codec_type'] == 'audio' for s in streams)
        if transcribe and not has_audio:
            raise ValueError('Nagranie nie zawiera dźwięku. Wyłącz transkrypcję, aby przygotować sam film.')
        transcript = None
        if transcribe:
            cached = folder / 'transcript.json'
            if cached.exists():
                transcript = json.loads(cached.read_text(encoding='utf-8'))
                if transcript.get('sourceSha256') != fingerprint or transcript.get('model') != model or transcript.get('language') != language:
                    transcript = None
            if transcript is None:
                self.report('Przygotowanie ścieżki audio na komputerze…')
                wav = folder / 'audio.wav'
                self.run([self.ffmpeg, '-nostdin', '-y', '-v', 'error', '-i', source, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav])
                config = dict(audio=str(wav), output=str(folder / 'recognition.json'), model=model, language=language,
                              device=device, duration=duration, sourceSha256=fingerprint)
                config_path = folder / 'recognition-config.json'
                atomic_json(config_path, config)
                command = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).with_name('main.py'))]
                self.report('Rozpoznawanie mowy. Pierwsze użycie pobiera model; kolejne działają lokalnie…')
                try:
                    self.run(command + ['--recognize', str(config_path)])
                except RuntimeError:
                    if device == 'cpu':
                        raise
                    self.report('GPU nie ukończyło rozpoznawania. Ponawiam na CPU z tym samym modelem…')
                    config['device'] = 'cpu'
                    atomic_json(config_path, config)
                    self.run(command + ['--recognize', str(config_path)])
                transcript = json.loads((folder / 'recognition.json').read_text(encoding='utf-8'))
                export_transcript(folder, transcript)
                wav.unlink(missing_ok=True)
        if not video:
            return folder, transcript
        stream = next((s for s in streams if s['codec_type'] == 'video'), None)
        if not stream:
            raise ValueError('W trybie strony wybierz plik zawierający obraz.')
        width, height = int(stream['width']), int(stream['height'])
        rotation = next((abs(int(s.get('rotation', 0))) for s in stream.get('side_data_list', []) if 'rotation' in s), 0)
        if rotation % 180 == 90:
            width, height = height, width
        width, height = width // 2 * 2, height // 2 * 2
        if min(width, height) < 2 or max(width, height) > 8192:
            raise ValueError('Rozdzielczość filmu nie jest obsługiwana.')
        rows = renditions(width, height, has_audio)
        estimated = sum(r['bitrate'] + r['audioBitrate'] for r in rows) * duration / 8 * 1.3
        if shutil.disk_usage(folder).free < estimated:
            raise RuntimeError(f'Za mało miejsca w folderze wyników. Potrzeba około {estimated / 1024**3:.1f} GB.')
        gpu = False
        if device != 'cpu':
            try:
                self.run([self.ffmpeg, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=256x256:d=0.1', '-c:v', 'h264_nvenc', '-f', 'null', '-'])
                gpu = True
            except RuntimeError:
                self.report('Brak dostępnego NVENC. Kodowanie na CPU (wolniej).')
        manifest = dict(protocol=1, sourceSha256=fingerprint, width=width, height=height, duration=duration, renditions=rows)
        for row in rows:
            self.report(f'Przygotowanie {row["label"]} — {"NVIDIA NVENC" if gpu else "CPU"}')
            variant = folder / row['label']
            variant.mkdir(exist_ok=True)
            checkpoint = variant / 'complete.json'
            if checkpoint.exists():
                saved = json.loads(checkpoint.read_text(encoding='utf-8'))
                if all((variant / f'segment_{i:06d}.ts').exists() for i in range(len(saved['durations']))):
                    row['durations'] = saved['durations']
                    continue
            for old in variant.glob('segment_*.ts'):
                old.unlink()
            def encode(acceleration):
                cuda = acceleration == 'cuda'
                args = [self.ffmpeg, '-nostdin', '-y', '-v', 'error', '-progress', 'pipe:1']
                if cuda:
                    args += ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
                args += ['-i', source, '-map', '0:v:0', '-map', '0:a:0?', '-sn', '-dn']
                scale = f'{"scale_cuda" if cuda else "scale"}={row["width"]}:{row["height"]}'
                args += ['-vf', scale + (':format=yuv420p' if cuda else ',format=yuv420p,setsar=1')]
                args += ['-c:v', 'h264_nvenc' if acceleration != 'cpu' else 'libx264', '-preset', 'p5' if acceleration != 'cpu' else 'veryfast']
                if acceleration == 'cpu':
                    args += ['-threads', str(max(1, min(8, (os.cpu_count() or 2) // 2))) ]
                args += ['-b:v', str(row['bitrate']), '-maxrate', str(row['bitrate']), '-bufsize', str(row['bitrate'] * 2),
                         '-force_key_frames', 'expr:gte(t,n_forced*6)', '-sc_threshold', '0', '-flags', '+cgop',
                         '-c:a', 'aac', '-b:a', str(row['audioBitrate'] or 96000), '-ac', '2', '-ar', '48000',
                         '-f', 'hls', '-hls_time', '6', '-hls_playlist_type', 'vod', '-hls_flags', 'independent_segments',
                         '-hls_segment_filename', str(variant / 'segment_%06d.ts'), str(variant / 'raw.m3u8')]
                self.run(args, duration)
            try:
                encode('cuda' if gpu else 'cpu')
            except RuntimeError:
                if not gpu:
                    raise
                self.report('Ten plik wymaga dekodowania na CPU. Nadal używam NVENC do kodowania…')
                try:
                    encode('nvenc')
                except RuntimeError:
                    self.report('GPU nie ukończyło kodowania. Ponawiam tę jakość na CPU…')
                    encode('cpu')
            row['durations'] = [float(d) for d in re.findall(r'#EXTINF:([\d.]+),', (variant / 'raw.m3u8').read_text())]
            if not row['durations'] or abs(sum(row['durations']) - duration) > 1:
                raise RuntimeError('Długość zakodowanego filmu nie zgadza się ze źródłem.')
            atomic_json(checkpoint, {'durations': row['durations']})
        self.report('Przygotowanie okładki i paczki gotowych plików…')
        self.run([self.ffmpeg, '-nostdin', '-y', '-v', 'error', '-ss', str(min(1, duration / 2)), '-i', source,
                  '-frames:v', '1', '-vf', "scale='min(1280,iw)':-2", '-q:v', '3', folder / 'poster.jpg'])
        paths = ['master.m3u8', 'poster.jpg']
        (folder / 'master.m3u8').write_text(playlist(manifest, 'master.m3u8'), encoding='utf-8', newline='\n')
        for row in rows:
            path = row['label'] + '/index.m3u8'
            (folder / path).write_text(playlist(manifest, path), encoding='utf-8', newline='\n')
            paths.append(path)
            paths += [f'{row["label"]}/segment_{i:06d}.ts' for i in range(len(row['durations']))]
        manifest['files'] = [dict(path=path, size=(folder / path).stat().st_size, sha256=digest(folder / path, self.cancel)) for path in paths]
        if any(f['size'] > 24 * 1024 * 1024 for f in manifest['files']):
            raise RuntimeError('Segment przekracza limit 24 MB.')
        if transcript:
            manifest['transcript'] = transcript
        atomic_json(folder / 'manifest.json', manifest)
        return folder, manifest


def recognize(config_path):
    """Isolated process: a native GPU failure cannot crash the editor or lose the job."""
    roots = [Path(getattr(sys, '_MEIPASS', Path(__file__).parent)), Path(sys.prefix) / 'Lib' / 'site-packages']
    handles = []
    for root in roots:
        for relative in ('nvidia/cublas/bin', 'nvidia/cudnn/bin'):
            location = root / relative
            if location.exists():
                os.environ['PATH'] = str(location) + os.pathsep + os.environ.get('PATH', '')
                if hasattr(os, 'add_dll_directory'):
                    handles.append(os.add_dll_directory(str(location)))
    from faster_whisper import WhisperModel
    import ctranslate2
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    gpu = config['device'] != 'cpu' and ctranslate2.get_cuda_device_count() > 0
    device = 'cuda' if gpu else 'cpu'
    print('LISTENACTIVE:Model ' + config['model'] + ' — ' + device.upper(), flush=True)
    model = WhisperModel(config['model'], device=device, compute_type='int8_float16' if gpu else 'int8',
                         cpu_threads=max(1, min(8, (os.cpu_count() or 2) // 2)), num_workers=1,
                         download_root=str(APP_DATA / 'models'))
    segments, _info = model.transcribe(config['audio'], language=None if config['language'] == 'auto' else config['language'],
                                     beam_size=5, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=400),
                                     condition_on_previous_text=False, word_timestamps=True, hallucination_silence_threshold=2.0)
    result, previous_end = [], 0
    for segment in segments:
        start = max(previous_end, round(max(0, segment.start), 3))
        end = min(round(config['duration'], 3), round(segment.end, 3))
        text = segment.text.strip()
        if text and end > start:
            result.append(dict(start=start, end=end, text=text))
            previous_end = end
        print(f'LISTENACTIVE:Rozpoznawanie mowy: {min(100, segment.end / config["duration"] * 100):.0f}%', flush=True)
    atomic_json(Path(config['output']), dict(sourceSha256=config['sourceSha256'], model=config['model'], language=config['language'], segments=result))
