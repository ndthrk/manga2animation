"""Tạo project từ bộ ảnh và YAML cho CLI hoặc notebook."""
import re
from pathlib import Path
import yaml
from ..settings import ROOT


def natural_key(path):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', Path(path).name)]


def import_project(store, cfg, name=None, max_pages=None):
    project = store.create(name or 'CLI • '+Path(cfg['input']).name)
    pid = project['id']
    store.config(pid, yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    source = ROOT / cfg['input']
    images = sorted([p for p in source.iterdir() if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp','.bmp')], key=natural_key)
    for image in images[:max_pages]:
        store.upload(pid, image.name, image.read_bytes())
    project = store.get(pid)
    for char in cfg.get('characters', []):
        char = dict(char)
        if char.get('image'):
            item = store.upload(pid, Path(char['image']).name, (ROOT/char['image']).read_bytes(), True)
            char['image'] = item['image']
        project['characters'].append(char)
    if cfg.get('global_prompt'):
        project['global_prompt'] = (ROOT / cfg['global_prompt']).read_text(encoding='utf-8')
    return store.update(pid, project)
