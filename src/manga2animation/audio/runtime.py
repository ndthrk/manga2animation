"""Giữ runtime ở RAM giữa các lượt sinh giọng, tự tắt khi hết thời gian chờ."""
import atexit
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from ..settings import ROOT, model_path
from ..storage import read_json, write_json


class OmniVoiceProvider:
    def __init__(self):
        self._process = None
        self._runtime_key = None
        self._timer = None
        self._generation = 0
        self._lock = threading.RLock()
        atexit.register(self.close)

    def close(self):
        with self._lock:
            self._generation += 1
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if self._process and self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=15)
            self._process = None

    def run(self, task_folder, settings, request, cancelled=None, progress=None):
        with self._lock:
            self._generation += 1
            generation = self._generation
            if self._timer:
                self._timer.cancel()
            folder = Path(task_folder)
            folder.mkdir(parents=True, exist_ok=True)
            config = settings['omnivoice']
            model = Path(model_path(config['model']))
            if not (model/'config.json').is_file() or not (model/'audio_tokenizer').is_dir():
                raise RuntimeError('Chưa đủ checkpoint OmniVoice: cần model/config.json và audio_tokenizer/. Xem docs/audio.md.')
            request = {**request, 'settings': settings, 'model_path': str(model), 'progress_file': str(folder/'progress.json'),
                       'asr_model_path': model_path(config.get('asr_model') or 'checkpoints/whisper-small'),
                       'python_path': model_path(config.get('python_path', 'vendor/omnivoice'))}
            payload, result, done = folder/'audio_request.json', folder/'audio_result.json', folder/'audio_done.json'
            done.unlink(missing_ok=True)
            result.unlink(missing_ok=True)
            write_json(payload, request)
            executable = config.get('python_executable') or sys.executable
            key = (executable, request['python_path'])
            if self._process is None or self._process.poll() is not None or self._runtime_key != key:
                self.close()
                generation = self._generation
                env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'PYTHONUTF8': '1'}
                worker = Path(__file__).with_name('worker.py')
                self._process = subprocess.Popen([executable, str(worker), '--serve'], cwd=ROOT, env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self._runtime_key = key
            process = self._process
            process.stdin.write(json.dumps([str(payload.resolve()), str(result.resolve()), str(done.resolve()), str((folder/'audio_worker.log').resolve())])+'\n')
            process.stdin.flush()
            start, last_progress = time.monotonic(), -1
            try:
                while not done.is_file():
                    if process.poll() is not None:
                        raise RuntimeError('Worker OmniVoice đã dừng trước khi hoàn tất. Xem audio_worker.log.')
                    if cancelled:
                        cancelled()
                    if progress and (folder/'progress.json').is_file():
                        try:
                            count = read_json(folder/'progress.json')['completed']
                            if count != last_progress:
                                progress(count)
                                last_progress = count
                        except (ValueError, PermissionError):
                            pass
                    if time.monotonic()-start > config['timeout_seconds']:
                        raise TimeoutError('OmniVoice quá thời gian chờ cấu hình.')
                    time.sleep(.1)
                if not read_json(done)['success']:
                    detail = (folder/'audio_worker.log').read_text(encoding='utf-8')[-2500:]
                    message = next((line.split(': ', 1)[-1] for line in reversed(detail.splitlines())
                                    if line.startswith(('ValueError:', 'RuntimeError:', 'FileNotFoundError:'))), '')
                    raise RuntimeError((message or 'Tác vụ OmniVoice thất bại.')+'\nChi tiết trong audio_worker.log:\n'+detail)
                return read_json(result)
            except BaseException:
                self.close()
                raise
            finally:
                if self._process is not None:
                    def idle_close():
                        with self._lock:
                            if generation == self._generation:
                                self.close()
                    self._timer = threading.Timer(max(0, min(300, config.get('keep_alive_seconds', 60))), idle_close)
                    self._timer.daemon = True
                    self._timer.start()
