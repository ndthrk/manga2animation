"""Kiểm tra môi trường hiện có; không tự cài gói hay tải model."""
import importlib.util
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')


def main():
    from manga2animation.services.models import prepare_runtime
    prepare_runtime()
    missing=[]
    print('Python:',sys.version.split()[0],sys.executable)
    for module in ['fastapi','uvicorn','multipart','yaml','PIL','numpy','torch','transformers','timm','einops','pulp','pytesseract','soundfile','scipy','googletrans']:
        found=importlib.util.find_spec(module) is not None
        print(('OK   ' if found else 'THIẾU'),module)
        if not found:missing.append(module)
    if importlib.util.find_spec('torch'):
        import torch
        print('PyTorch:',torch.__version__,'· CUDA:',torch.cuda.is_available())
        if torch.cuda.is_available():print('GPU:',torch.cuda.get_device_name(0))
    from manga2animation.settings import read_config
    cfg=read_config()
    for relative in [cfg['upscale']['model'],cfg['magi']['model']+'/config.json',cfg['magi']['model']+'/pytorch_model.bin',cfg['magi']['processor']+'/preprocessor_config.json','frontend/dist/index.html']:
        present=(ROOT/relative).is_file();print('OK   ' if present else 'THIẾU',relative)
        if not present:missing.append(relative)
    command=cfg['ocr']['tesseract'].get('command') or shutil.which('tesseract')
    print('Tesseract:',command or 'Chưa có trên PATH. Điền ocr.tesseract.command trong configs/pipeline.yaml.')
    if command and importlib.util.find_spec('pytesseract'):
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd=command
        print('Ngôn ngữ Tesseract đã cài:',pytesseract.get_languages(config=''))
    elif cfg['ocr']['enabled'] and cfg['ocr']['engine']=='tesseract':missing.append('Tesseract executable')
    from manga2animation.services.video import ffmpeg_path
    import subprocess
    try:
        command=ffmpeg_path();result=subprocess.run([command,'-filters'],capture_output=True,text=True)
        print('FFmpeg:',command,'· có libass:',bool(' ass ' in result.stdout))
    except ValueError as exc:print(exc);missing.append('FFmpeg')
    print('Hoàn tất. '+('Cần bổ sung '+str(len(missing))+' mục ở trên.' if missing else 'Có thể chạy python run.py.'))
    return bool(missing)


if __name__=='__main__':raise SystemExit(main())
