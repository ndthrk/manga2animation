"""Chạy UI hoặc trích xuất bằng cùng dịch vụ, không cần cài package dự án."""
import argparse
from pathlib import Path
from .settings import ROOT, read_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command')
    web = commands.add_parser('web', help='Mở trình biên tập local (mặc định)')
    web.add_argument('--port', type=int, default=8000)
    web.add_argument('--no-browser', action='store_true')
    extract_cmd = commands.add_parser('extract', help='Trích xuất theo YAML')
    extract_cmd.add_argument('--config', type=Path, help='YAML; project có sẵn mặc định dùng cấu hình đã lưu của project')
    extract_cmd.add_argument('--project', help='ID project có sẵn, nếu bỏ trống sẽ tạo mới')
    extract_cmd.add_argument('--full', action='store_true', help='Xử lý lại toàn bộ, tạo timeline mới từ kết quả model')
    extract_cmd.add_argument('--base-run', help='Dùng kết quả và bản chỉnh sửa của lần Extract được chọn')
    args = parser.parse_args(argv)
    if args.command in (None, 'web'):
        import threading
        import webbrowser
        import uvicorn
        from .api import create_app
        port = getattr(args, 'port', 8000)
        if not getattr(args, 'no_browser', False):
            threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
        uvicorn.run(create_app(), host='127.0.0.1', port=port)
        return
    import yaml
    from .storage import ProjectStore
    from .services.extraction import extract
    from .services.projects import import_project
    store = ProjectStore()
    from .settings import validate_config
    cfg = validate_config(yaml.safe_load(store.config(args.project))) if args.project and args.config is None else read_config(args.config)
    project = store.get(args.project) if args.project else import_project(store, cfg)
    pid = project['id']
    store.config(pid, yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    folder = store.new_run(pid, base_run_id=args.base_run, force=args.full)
    print('Project:', pid, '\nExtract:', folder)
    from .storage import read_json
    plan = read_json(folder/'status.json')
    print(f"Dùng lại {plan['reused_pages']} trang · Cần xử lý {plan['processing_pages']} trang")
    extract(folder, progress=lambda s: print(f"{s['stage']}: {s['page']}/{s['total']}", flush=True))
