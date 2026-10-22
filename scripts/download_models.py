"""Tải bộ model tối thiểu hoặc model giọng local; không thay đổi thư viện Python."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import requests

ROOT=Path(__file__).resolve().parents[1]
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')


def fetch(url,path,expected=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        with path.open('rb') as handle:
            if not expected or hashlib.file_digest(handle,'sha256').hexdigest()==expected:return
    temporary=path.with_suffix(path.suffix+'.partial')
    print('Đang tải:',path.relative_to(ROOT),flush=True)
    with requests.get(url,stream=True,timeout=(30,180)) as response:
        response.raise_for_status()
        with temporary.open('wb') as handle:
            for block in response.iter_content(1024*1024):handle.write(block)
    if expected:
        with temporary.open('rb') as handle:
            if hashlib.file_digest(handle,'sha256').hexdigest()!=expected:raise ValueError('SHA256 sai: '+str(path))
    temporary.replace(path)


def snapshot(repo,directory,processor=False):
    response=requests.get(f'https://huggingface.co/api/models/{repo}?blobs=true',timeout=60)
    response.raise_for_status();meta=response.json();items=meta['siblings']
    names={i['rfilename'] for i in items};revision=meta['sha']
    # Chỉ tải một định dạng trọng số. Processor chỉ cần config và tokenizer.
    weights='model.safetensors' if 'model.safetensors' in names else 'pytorch_model.bin'
    selected=[i for i in items if i['rfilename']==weights and not processor or i['rfilename'].endswith(('.json','.py','.txt','.jinja','.model','.md')) or 'LICENSE' in i['rfilename']]
    for item in selected:
        name=item['rfilename']
        if name.startswith('.') or '..' in Path(name).parts:continue
        fetch(f'https://huggingface.co/{repo}/resolve/{revision}/{name}',ROOT/directory/name,item.get('lfs',{}).get('sha256'))
    (ROOT/directory/'download_manifest.json').write_text(json.dumps({'repo':repo,'revision':revision,'files':selected},indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audio',action='store_true',help='Tải OmniVoice, codec và Whisper thay bộ Extract.')
    args=parser.parse_args()
    if args.audio:
        snapshot('k2-fsa/OmniVoice','checkpoints/omnivoice')
        snapshot('eustlb/higgs-audio-v2-tokenizer','checkpoints/omnivoice/audio_tokenizer')
        snapshot('openai/whisper-small','checkpoints/whisper-small')
    else:
        fetch('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth',ROOT/'checkpoints/realesrgan/realesr-animevideov3.pth')
        snapshot('ragavsachdeva/magiv2','checkpoints/magiv2')
        snapshot('microsoft/trocr-base-printed','checkpoints/trocr-processor',processor=True)
    print('Hoàn tất. Thông tin giấy phép: third_party/README.md.')


if __name__=='__main__':main()
