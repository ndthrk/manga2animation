"""Worker độc lập: nạp duy nhất OmniVoice, ghi WAV và báo thời lượng đo thực tế."""
import json
import os
import sys
from pathlib import Path
import time

_cached_model = None
_cached_key = None


def load_voice_model(request, runtime, torch, model_class):
    """Giữ model ở RAM khi chờ; chỉ chuyển lên GPU trong lượt xử lý đang giữ khóa."""
    global _cached_model, _cached_key
    key = (request['model_path'], runtime['dtype'], runtime['device'])
    if _cached_model is not None and _cached_key == key:
        print('Dùng lại OmniVoice đã nạp, chuyển model từ RAM lên thiết bị.', flush=True)
        _cached_model.to(runtime['device'])
        return _cached_model
    _cached_model = None
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    _cached_model = model_class.from_pretrained(request['model_path'], device_map=runtime['device'],
                       dtype=getattr(torch, runtime['dtype']), local_files_only=True,
                       asr_model_name=runtime.get('asr_model') or None, asr_device=runtime['asr_device'])
    _cached_key = key
    return _cached_model


def resolve_reference_text(request, transcriber):
    """Ưu tiên lời người dùng nhập; chỉ nhận dạng khi ô chép lời để trống."""
    text = request.get('reference_text', '').strip()
    if text:
        return text, 'manual'
    text = transcriber(request['reference_audio']).strip()
    if not text:
        raise ValueError('Không nhận ra lời nói trong âm thanh mẫu. Hãy chọn đoạn nói rõ hơn hoặc nhập bản chép lời.')
    return text, 'whisper'


def transcribe_reference(audio_path, model_path, device):
    """Chạy Whisper trước OmniVoice, giải phóng model kể cả khi nhận dạng lỗi."""
    import gc
    import numpy as np
    import soundfile as sf
    import librosa
    import torch
    from transformers import pipeline

    model_path = Path(model_path)
    if not (model_path/'model.safetensors').is_file():
        raise ValueError('Thiếu Whisper local để tự chép lời. Cần checkpoint tại '+str(model_path)+'.')
    audio, rate = sf.read(audio_path, dtype='float32', always_2d=True)
    audio = audio.mean(axis=1)
    if not audio.size or not np.isfinite(audio).all():
        raise ValueError('Âm thanh mẫu rỗng hoặc dữ liệu không hợp lệ.')
    audio = librosa.resample(audio, orig_sr=rate, target_sr=16000) if rate != 16000 else audio
    recognizer = None
    try:
        print('Tự chép lời bằng Whisper:', device, flush=True)
        recognizer = pipeline('automatic-speech-recognition', model=str(model_path),
                              device=device, dtype=torch.float16 if str(device).startswith('cuda') else torch.float32)
        with torch.inference_mode():
            return recognizer({'array': audio, 'sampling_rate': 16000},
                              chunk_length_s=30, batch_size=1, generate_kwargs={'task': 'transcribe'})['text']
    finally:
        del recognizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def main(payload_path, result_path):
    started = time.monotonic()
    request = json.loads(Path(payload_path).read_text(encoding='utf-8'))
    vendor = Path(request['python_path'])
    if vendor.is_dir():
        sys.path.insert(0, str(vendor))
    try:
        import torch
        import soundfile as sf
        from omnivoice import OmniVoice, VoiceClonePrompt
    except ImportError as exc:
        raise RuntimeError('Thiếu thư viện OmniVoice hoặc Transformers tương thích ở runtime âm thanh. Xem docs/audio.md.') from exc
    settings, runtime = request['settings'], request['settings']['omnivoice']
    languages = json.loads((Path(__file__).parents[1]/'data'/'languages.json').read_text(encoding='utf-8'))
    language = next((item.get('audio_code', item['code']) for item in languages if item['code'] == settings['language']), settings['language'])
    torch.set_num_threads(max(1, int(runtime.get('threads', 4))))
    # Báo rõ lỗi CUDA để không vô tình chờ tác vụ chạy chậm trên CPU.
    if runtime['device'].startswith('cuda') and not torch.cuda.is_available():
        raise RuntimeError('Đã chọn GPU cho OmniVoice nhưng PyTorch không nhận CUDA. Kiểm tra driver và bản PyTorch CUDA.')
    if runtime['device'].startswith('cuda'):
        print('OmniVoice GPU:', torch.cuda.get_device_name(torch.device(runtime['device'])), flush=True)
    transcript, transcript_source = '', ''
    if request['operation'] == 'clone':
        transcript, transcript_source = resolve_reference_text(request, lambda audio: transcribe_reference(
            audio, request['asr_model_path'], runtime['asr_device']))
    model = load_voice_model(request, runtime, torch, OmniVoice)
    print(f'OmniVoice: {model.device}, {model.dtype}; audio tokenizer: {model.audio_tokenizer.device}', flush=True)
    generation = {key: settings[key] for key in ('num_step', 'guidance_scale', 'position_temperature',
                  'class_temperature', 'denoise', 'preprocess_prompt', 'postprocess_output')}
    result = {}
    with torch.inference_mode():
        if request['operation'] == 'clone':
            prompt = model.create_voice_clone_prompt(ref_audio=request['reference_audio'], ref_text=transcript,
                                                     preprocess_prompt=settings['preprocess_prompt'])
            prompt.save(request['prompt_output'])
            clips = model.generate(text=request['preview_text'], voice_clone_prompt=prompt,
                                   language=language, speed=settings['speed'], **generation)
            sf.write(request['preview_output'], clips[0], model.sampling_rate)
            result = {'prompt': request['prompt_output'], 'preview': request['preview_output'],
                      'duration': len(clips[0])/model.sampling_rate, 'sample_rate': model.sampling_rate,
                      'reference_text': transcript, 'reference_text_source': transcript_source}
        else:
            prompts = {}
            results = []
            items = request['items']
            size = settings['batch_size']
            for start in range(0, len(items), size):
                chunk = items[start:start+size]
                for item in chunk:
                    if item['prompt'] not in prompts:
                        prompts[item['prompt']] = VoiceClonePrompt.load(item['prompt'])
                clips = model.generate(text=[item['text'] for item in chunk],
                                       voice_clone_prompt=[prompts[item['prompt']] for item in chunk],
                                       language=language, speed=settings['speed'], **generation)
                if len(clips) != len(chunk):
                    raise RuntimeError('OmniVoice trả thiếu clip so với số câu yêu cầu.')
                for item, clip in zip(chunk, clips):
                    sf.write(item['output'], clip, model.sampling_rate)
                    results.append({'id': item['id'], 'path': item['output'], 'duration': len(clip)/model.sampling_rate,
                                    'sample_rate': model.sampling_rate})
                Path(request['progress_file']).write_text(json.dumps({'completed': len(results)}), encoding='utf-8')
            result = {'clips': results}
    result['worker_seconds'] = round(time.monotonic()-started, 3)
    Path(result_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


def serve():
    """Nhận nhiều tác vụ từ cùng backend; sau mỗi tác vụ trả toàn bộ VRAM cho pipeline."""
    import contextlib
    import traceback
    global _cached_model, _cached_key
    for line in sys.stdin:
        payload, result, done, log_path = json.loads(line)
        state = {'success': False}
        with Path(log_path).open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                main(payload, result)
                state['success'] = True
            except BaseException:
                traceback.print_exc()
                _cached_model = None
                _cached_key = None
            finally:
                import torch
                import gc
                if _cached_model is not None:
                    _cached_model.to('cpu')
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        Path(done).write_text(json.dumps(state), encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1:] == ['--serve']:
        serve()
    else:
        main(*sys.argv[1:])
