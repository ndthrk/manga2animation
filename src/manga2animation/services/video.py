"""Xuất MP4 trình chiếu bằng FFmpeg, ghép clip theo thứ tự thoại của từng panel."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import math
import os
import shutil
import subprocess
import time
from ..storage import read_json, write_json, safe_path, uid, now
from .cancellation import check_cancel, ExtractionCancelled
from .timing import valid_audio
from .subtitles import validate_subtitles, captions, write_ass, fonts


def ffmpeg_path():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise ValueError('Cần cài FFmpeg hoặc imageio-ffmpeg để xuất video.') from exc


def validate_video(options):
    value = {**{'width': 1280, 'height': 720, 'fps': 24, 'crf': 23,
                'include_audio': True, 'extend_for_audio': True, 'background': '#111111'}, **options}
    for key in ('width', 'height'):
        if not isinstance(value[key], int) or value[key] % 2 or not 64 <= value[key] <= 3840:
            raise ValueError('Kích thước video phải là số chẵn từ 64 đến 3840 pixel.')
    if value['fps'] not in (12, 24, 25, 30, 60) or not isinstance(value['crf'], int) or not 16 <= value['crf'] <= 35:
        raise ValueError('FPS hoặc chất lượng video không hợp lệ.')
    import re
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(value['background'])):
        raise ValueError('Màu nền video phải có dạng #RRGGBB.')
    for key in ('include_audio', 'extend_for_audio'):
        if not isinstance(value[key], bool):
            raise ValueError('Cấu hình âm thanh video phải là boolean.')
    value['subtitles']=validate_subtitles(value.get('subtitles'))
    return value


def panel_audio(project_folder, panel, options, voices=None, gap=.2, with_intervals=False):
    """Trả dữ liệu mono 48 kHz; không cắt tiếng trừ khi người dùng chọn giữ thời lượng."""
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    clips, missing = [], []
    for line in panel['dialogues']:
        if not options['include_audio']:
            break
        if not valid_audio(line, voices):
            if line.get('text', '').strip():
                missing.append(line['id'])
            continue
        path = safe_path(project_folder, line['audio']['path'])
        if not path.is_file():
            missing.append(line['id'])
            continue
        data, rate = sf.read(path, dtype='float32', always_2d=True)
        data = data.mean(axis=1)
        edit = line.get('audio_edit', {})
        if edit.get('muted'):
            continue
        start = max(0, min(len(data), round(float(edit.get('start', 0))*rate)))
        end = max(start, min(len(data), round(float(edit.get('end', len(data)/rate))*rate)))
        data = data[start:end]*max(0, min(2, float(edit.get('volume', 1))))
        ratio = Fraction(48000, rate)
        if rate != 48000:
            data = resample_poly(data, ratio.numerator, ratio.denominator).astype('float32')
        clips.append((line['id'], data))
    audio_length = sum(len(c) for _, c in clips)/48000 + max(0, len(clips)-1)*gap
    seconds = max(float(panel['duration']), audio_length) if options['extend_for_audio'] else float(panel['duration'])
    # Làm tròn theo khung hình để âm thanh và ảnh không tích lũy sai lệch sau khi nối.
    seconds = math.ceil(seconds*options['fps'])/options['fps']
    mixed = np.zeros(round(seconds*48000), dtype='float32')
    position = 0
    intervals={}
    for ident, clip in clips:
        length = min(len(clip), max(0, len(mixed)-position))
        mixed[position:position+length] = clip[:length]
        if length:intervals[ident]=[position/48000,(position+length)/48000]
        position += len(clip)+round(gap*48000)
    return (mixed, seconds, missing, intervals) if with_intervals else (mixed, seconds, missing)


def run_ffmpeg(command, folder, log_path):
    with log_path.open('a', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=folder, stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            while process.poll() is None:
                check_cancel(folder)
                time.sleep(.15)
        except BaseException:
            process.terminate()
            process.wait(timeout=15)
            raise
    if process.returncode:
        raise RuntimeError('FFmpeg không xuất được video:\n'+log_path.read_text(encoding='utf-8', errors='replace')[-1500:])


def submit_video(store, executor, pid, rid, options):
    options = validate_video(options)
    with store.lock:
        project = store.get(pid)
        run = store.run_folder(pid, rid)
        manifest = read_json(run/'manifest.json')
        edits = store.edits(run)
        order = [ident for ident in edits['order'] if not edits['panels'][ident]['hidden']]
        if not order:
            raise ValueError('Timeline chưa có panel để tạo video.')
        folder = store.folder(pid)/'videos'/uid()
        folder.mkdir(parents=True)
        source_panels = {p['id']: p for page in manifest['pages'] for p in page['panels']}
        frames = []
        selected_fonts={}
        # Chụp cả ảnh/clip cần dùng để vẫn render được khi lần Extract gốc được chuyển thùng rác.
        for index, ident in enumerate(order):
            panel = deepcopy(edits['panels'][ident])
            subtitle_options=validate_subtitles({**options['subtitles'],**panel.get('subtitle_settings',{})})
            if subtitle_options['enabled']:
                family=subtitle_options['font']
                installed=next((font for font in fonts() if font['name']==family),None)
                if not installed:raise ValueError(f'Chưa cài font phụ đề: {family}. Hãy chọn font có trên máy.')
                selected_fonts[family]=installed['path']
            source = safe_path(run, source_panels[ident]['image'])
            image = folder/f'{index:05d}.png'
            shutil.copy2(source, image)
            for line in panel['dialogues']:
                clip = line.get('audio')
                if clip and safe_path(store.folder(pid), clip['path']).is_file():
                    dest = folder/'clips'/(uid()+'.wav')
                    dest.parent.mkdir(exist_ok=True)
                    shutil.copy2(safe_path(store.folder(pid), clip['path']), dest)
                    clip['path'] = str(dest.relative_to(store.folder(pid))).replace('\\', '/')
            frames.append({'id': ident, 'image': image.name, 'edit': panel})
        for index,path in enumerate(selected_fonts.values()):
            target=folder/'fonts'/(str(index)+Path(path).suffix)
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path,target)
        cfg = __import__('yaml').safe_load(store.config(pid))
        request = {'run_id': rid, 'project_revision': project['revision'], 'edits_revision': edits['revision'],
                   'frames': frames, 'options': options, 'characters': project['characters'],
                   'unknown_character': project.get('unknown_character'), 'gap': cfg['timing']['dialogue_gap']}
        write_json(folder/'request.json', request)
        status = {'id': folder.name, 'state': 'queued', 'completed': 0, 'total': len(frames), 'created_at': now(), 'pid': os.getpid()}
        write_json(folder/'status.json', status)
        executor.submit(render_video, store.folder(pid), folder)
        return status


def render_video(project_folder, folder):
    import soundfile as sf
    state = read_json(folder/'status.json')
    request = read_json(folder/'request.json')
    options = request['options']
    durations, missing, subtitle_rows, subtitle_warnings = [], [], [], []
    try:
        exe = ffmpeg_path()
        state['state'] = 'running'
        write_json(folder/'status.json', state)
        characters = request['characters']+([request['unknown_character']] if request.get('unknown_character') else [])
        voices = {c['id']: c.get('voice', {}).get('prompt') for c in characters}
        colors={c['id']:c['color'] for c in characters}
        for frame in request['frames']:
            check_cancel(folder)
            panel = frame['edit']
            for line in panel['dialogues']:
                if line['speaker_id'] not in voices:
                    voices[line['speaker_id']] = voices.get('unknown')
            audio, seconds, absent, intervals = panel_audio(project_folder, panel, options, voices,
                                                  panel.get('timing', {}).get('dialogue_gap', request['gap']), with_intervals=True)
            rows=captions(panel,seconds,options['subtitles'],colors,intervals)
            subtitle_cfg=validate_subtitles({**options['subtitles'],**panel.get('subtitle_settings',{})})
            if subtitle_cfg['enabled'] and subtitle_cfg['text_source']=='translation':
                from .timing import dialogue_text
                subtitle_warnings.extend({'panel_id':frame['id'],'dialogue_id':line['id'],'language':subtitle_cfg['translation_language']}
                    for line in panel['dialogues'] if line.get('text','').strip() and not dialogue_text(line,'translation',subtitle_cfg['translation_language']).strip())
            offset=sum(d['seconds'] for d in durations)
            subtitle_rows.extend({**row,'panel_id':frame['id'],'start':round(row['start']+offset,2),'end':round(row['end']+offset,2)} for row in rows)
            missing.extend(absent)
            durations.append({'panel_id': frame['id'], 'seconds': seconds})
            audio_path = folder/'mixed.wav'
            sf.write(audio_path, audio, 48000)
            segment = folder/f"segment_{state['completed']:05d}.mp4"
            vf = f"scale={options['width']}:{options['height']}:force_original_aspect_ratio=decrease,pad={options['width']}:{options['height']}:(ow-iw)/2:(oh-ih)/2:color={options['background']},setsar=1,format=yuv420p"
            if rows:
                name=f"subtitles_{state['completed']:05d}.ass"
                write_ass(folder/name,rows,options['width'],options['height'])
                vf+=f",ass=filename={name}:fontsdir=fonts"
            command = [exe, '-nostdin', '-y', '-loop', '1', '-framerate', str(options['fps']), '-i', str(folder/frame['image']),
                       '-i', str(audio_path), '-t', str(seconds), '-vf', vf, '-r', str(options['fps']),
                       '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'stillimage', '-crf', str(options['crf']),
                       '-c:a', 'aac', '-b:a', '160k', '-ac', '2', '-ar', '48000', str(segment)]
            run_ffmpeg(command, folder, folder/'ffmpeg.log')
            state['completed'] += 1
            write_json(folder/'status.json', state)
        listing = folder/'segments.txt'
        listing.write_text(''.join(f"file 'segment_{i:05d}.mp4'\n" for i in range(len(request['frames']))), encoding='utf-8')
        result = folder/'slideshow.mp4'
        run_ffmpeg([exe, '-nostdin', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(result)], folder, folder/'ffmpeg.log')
        state.update(state='completed', video=str(result.relative_to(project_folder)).replace('\\','/'),
                     duration=sum(d['seconds'] for d in durations), panel_durations=durations,
                     missing_audio=missing, subtitle_warnings=subtitle_warnings, options=options)
        if subtitle_rows:
            write_json(folder/'subtitles.json',subtitle_rows)
            write_ass(folder/'subtitles.ass',subtitle_rows,options['width'],options['height'])
            state['subtitles']=str((folder/'subtitles.ass').relative_to(project_folder)).replace('\\','/')
        # Giữ snapshot request/ảnh/clip; xóa bản video trung gian để tránh nhân đôi dung lượng.
        for path in list(folder.glob('segment_*.mp4'))+[folder/'mixed.wav']:
            path.unlink(missing_ok=True)
    except ExtractionCancelled as exc:
        state.update(state='cancelled', error=str(exc))
    except Exception as exc:
        state.update(state='failed', error=str(exc))
    finally:
        state['updated_at'] = now()
        write_json(folder/'status.json', state)
