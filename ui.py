import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from engine import APP_DATA, VERSION, Cancelled, Engine, SiteClient, atomic_json, validate_job


class ListenActive(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=24)
        self.root = root
        self.pack(fill='both', expand=True)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.result = None
        self.settings_path = APP_DATA / 'settings.json'
        self.source = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / 'Videos' / 'ListenActive'))
        self.job_path = tk.StringVar()
        self.mode = tk.StringVar(value='transcript')
        self.device = tk.StringVar(value='Automatycznie — NVIDIA lub CPU')
        self.model = tk.StringVar(value='large-v3 — najwyższa dokładność')
        self.language = tk.StringVar(value='pl')
        self.with_transcript = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='Wybierz nagranie, aby rozpocząć.')
        self.site = tk.StringVar(value='Nie wybrano zadania lekcji.')
        self.controls = []
        try:
            settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
            self.destination.set(settings.get('destination', self.destination.get()))
        except (OSError, ValueError):
            pass
        ttk.Label(self, text='ListenActive', font=('Segoe UI', 25, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Twoje nagrania. Obliczenia na Twoim komputerze.', font=('Segoe UI', 11)).pack(anchor='w', pady=(4, 20))
        modes = ttk.Frame(self)
        modes.pack(fill='x')
        for value, label in [('transcript', '1. Transkrypcja do SRT i TXT'), ('website', '2. Pełna obsługa strony')]:
            button = ttk.Radiobutton(modes, text=label, variable=self.mode, value=value, command=self.change_mode)
            button.pack(side='left', padx=(0, 28))
            self.controls.append(button)
        self.file_row('Nagranie audio lub wideo', self.source, self.choose_source)
        self.file_row('Folder gotowych materiałów', self.destination, self.choose_destination)
        self.website_box = ttk.LabelFrame(self, text='Połączenie ze stroną', padding=12)
        self.file_row('Plik zadania .redaktor.json', self.job_path, self.choose_job, parent=self.website_box)
        ttk.Label(self.website_box, textvariable=self.site, wraplength=680).pack(anchor='w', pady=6)
        check = ttk.Checkbutton(self.website_box, text='Przygotuj transkrypcję razem z filmem', variable=self.with_transcript)
        check.pack(anchor='w')
        self.controls.append(check)
        self.options = ttk.LabelFrame(self, text='Przetwarzanie lokalne', padding=12)
        self.options.pack(fill='x', pady=(12, 8))
        for name, variable, values, width in [
            ('Sprzęt', self.device, ['Automatycznie — NVIDIA lub CPU', 'CPU — słabszy komputer'], 36),
            ('Model', self.model, ['large-v3 — najwyższa dokładność', 'large-v3-turbo — szybciej', 'small — mniej pamięci'], 36),
            ('Język', self.language, ['pl', 'auto', 'en', 'de', 'uk'], 10),
        ]:
            row = ttk.Frame(self.options)
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=name, width=10).pack(side='left')
            box = ttk.Combobox(row, textvariable=variable, values=values, state='readonly', width=width)
            box.pack(side='left')
            self.controls.append(box)
        ttk.Label(self.options, text='RTX 4070 Ti: NVIDIA NVENC i CUDA. Bez zgodnego GPU: CPU, ten sam dokładny model.\nPierwsze użycie pobiera narzędzia i model (kilka GB). Nagranie pozostaje na komputerze.', wraplength=700).pack(anchor='w', pady=(10, 0))
        actions = ttk.Frame(self)
        actions.pack(fill='x', pady=12)
        self.start_button = ttk.Button(actions, text='Generuj SRT i TXT', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='Zatrzymaj', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=10)
        ttk.Button(actions, text='Otwórz wyniki', command=self.open_results).pack(side='left')
        self.progress = ttk.Progressbar(self, mode='indeterminate')
        self.progress.pack(fill='x')
        ttk.Label(self, textvariable=self.status, wraplength=700).pack(anchor='w', pady=8)
        self.log = tk.Text(self, height=8, wrap='word', state='disabled', font=('Consolas', 9))
        self.log.pack(fill='both', expand=True)
        ttk.Label(self, text=f'Windows 10/11 x64 · ListenActive {VERSION} · Kod aplikacji: MIT').pack(anchor='w', pady=(10, 0))
        self.root.winfo_toplevel().protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.poll)

    def file_row(self, title, variable, command, parent=None):
        parent = parent or self
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=(12, 0))
        ttk.Label(row, text=title).pack(anchor='w')
        line = ttk.Frame(row)
        line.pack(fill='x', pady=4)
        entry = ttk.Entry(line, textvariable=variable)
        entry.pack(side='left', fill='x', expand=True)
        button = ttk.Button(line, text='Wybierz…', command=command)
        button.pack(side='left', padx=(8, 0))
        self.controls.extend([entry, button])

    def change_mode(self):
        if self.mode.get() == 'website':
            self.website_box.pack(fill='x', pady=8, before=self.options)
            self.start_button.configure(text='Przygotuj i prześlij na stronę')
        else:
            self.website_box.pack_forget()
            self.start_button.configure(text='Generuj SRT i TXT')

    def choose_source(self):
        path = filedialog.askopenfilename(title='Wybierz nagranie', filetypes=[('Nagrania', '*.mp4 *.mkv *.mov *.webm *.mp3 *.wav *.m4a *.ogg *.flac *.avi'), ('Wszystkie pliki', '*.*')])
        if path:
            self.source.set(path)

    def choose_destination(self):
        path = filedialog.askdirectory(title='Folder wyników')
        if path:
            self.destination.set(path)

    def choose_job(self):
        path = filedialog.askopenfilename(title='Zadanie pobrane ze strony', filetypes=[('Zadanie ListenActive', '*.redaktor.json'), ('JSON', '*.json')])
        if path:
            self.job_path.set(path)
            try:
                job = self.load_job()
                self.site.set(f'Strona: {job["apiUrl"]}\nLekcja: {job.get("title", "")} · {job["kind"]}')
            except (ValueError, OSError) as exc:
                messagebox.showerror('Zadanie', str(exc))

    def load_job(self):
        path = Path(self.job_path.get())
        if path.stat().st_size > 16384:
            raise ValueError('Plik zadania jest nieprawidłowy.')
        return validate_job(json.loads(path.read_text(encoding='utf-8-sig')))

    def start(self):
        if self.running:
            return
        try:
            if not self.source.get() or not Path(self.source.get()).is_file():
                raise ValueError('Wybierz plik nagrania.')
            if not self.destination.get().strip():
                raise ValueError('Wybierz folder wyników.')
            job = self.load_job() if self.mode.get() == 'website' else None
            source = self.source.get()
            destination = self.destination.get()
            model = self.model.get().split(' — ')[0]
            device = 'cpu' if self.device.get().startswith('CPU') else 'auto'
            language = self.language.get()
            with_transcript = self.with_transcript.get() if job and job['kind'] == 'video' else True
            APP_DATA.mkdir(parents=True, exist_ok=True)
            atomic_json(self.settings_path, {'destination': destination})
            if job:
                self.site.set(f'Strona: {job["apiUrl"]}\nLekcja: {job.get("title", "")} · {job["kind"]}')
        except (ValueError, OSError) as exc:
            messagebox.showerror('ListenActive', str(exc))
            return
        self.cancel.clear()
        self.running = True
        for control in self.controls:
            control.configure(state='disabled')
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.progress.start(15)
        def work():
            report = lambda text: self.events.put(('log', text))
            try:
                site = SiteClient(job, self.cancel, report) if job else None
                if site:
                    state = site.request('GET')
                    if state['completed']:
                        self.events.put(('done', 'Zadanie jest już ukończone na stronie.'))
                        return
                    if state['stale']:
                        raise RuntimeError('Pobierz nowe zadanie — film zmienił się na stronie.')
                engine = Engine(report, self.cancel)
                folder, result = engine.prepare(source, destination, video=bool(job and job['kind'] == 'video'),
                                                transcribe=with_transcript, device=device, model=model, language=language)
                self.result = folder
                if site:
                    if job['kind'] == 'video':
                        site.upload(folder, result)
                    else:
                        site.request('POST', '/transcript', result)
                self.events.put(('done', 'Gotowe. Materiały są na stronie.' if site else 'Gotowe. Zapisano transcript.srt i transcript.txt.'))
            except Cancelled:
                self.events.put(('done', 'Zatrzymano. Gotowe jakości i pliki zachowano. Uruchom ponownie, aby wznowić.'))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        self.cancel.set()
        self.status.set('Zatrzymywanie… Gotowe pliki zostaną zachowane.')
        self.stop_button.configure(state='disabled')

    def poll(self):
        while True:
            try:
                kind, text = self.events.get_nowait()
            except queue.Empty:
                break
            self.status.set(text if len(text) < 250 else text[:250])
            self.log.configure(state='normal')
            self.log.insert('end', text + '\n')
            self.log.see('end')
            self.log.configure(state='disabled')
            if kind in ('done', 'error'):
                self.running = False
                self.progress.stop()
                self.start_button.configure(state='normal')
                self.stop_button.configure(state='disabled')
                for control in self.controls:
                    control.configure(state='readonly' if isinstance(control, ttk.Combobox) else 'normal')
                if kind == 'error':
                    messagebox.showerror('ListenActive — nie ukończono zadania', text)
        self.root.after(100, self.poll)

    def open_results(self):
        folder = self.result or Path(self.destination.get())
        if folder.is_dir():
            os.startfile(str(folder))

    def close(self):
        if self.running:
            if messagebox.askyesno('ListenActive', 'Zatrzymać pracę? Gotowe pliki zostaną zachowane.'):
                self.stop()
                self.root.after(300, self.close_when_stopped)
        else:
            self.root.destroy()

    def close_when_stopped(self):
        if self.running:
            self.root.after(300, self.close_when_stopped)
        else:
            self.root.destroy()


def main():
    if getattr(sys, 'frozen', False):
        import ctypes
        window = ctypes.windll.kernel32.GetConsoleWindow()
        if window:
            ctypes.windll.user32.ShowWindow(window, 0)
    root = tk.Tk()
    root.title('ListenActive')
    root.geometry('830x850')
    root.minsize(760, 600)
    style = ttk.Style()
    style.theme_use('vista' if 'vista' in style.theme_names() else 'clam')
    style.configure('.', font=('Segoe UI', 10))
    canvas = tk.Canvas(root, highlightthickness=0)
    scroll = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    scroll.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    inner = ttk.Frame(canvas)
    window = canvas.create_window((0, 0), window=inner, anchor='nw')
    app = ListenActive(inner)
    app.root = root
    root.protocol('WM_DELETE_WINDOW', app.close)
    inner.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
    root.bind_all('<MouseWheel>', lambda event: canvas.yview_scroll(int(-event.delta / 120), 'units') if event.widget != app.log else None)
    root.mainloop()
