"""Tổng hợp hàng đợi từ trạng thái trên đĩa, kể cả khi đổi project."""
from ..storage import read_json, safe_path


def list_jobs(store):
    jobs = []
    for project in store.list():
        root = store.folder(project['id'])
        patterns = [('extract', 'extracts/*/status.json'), ('task', 'tasks/*/status.json'),
                    ('video', 'videos/*/status.json'), ('ocr', 'extracts/*/proposals/*.json')]
        for kind, pattern in patterns:
            for path in root.glob(pattern):
                item = read_json(path)
                run_id = path.parents[1].name if kind == 'ocr' else item.get('run_id')
                jobs.append({**item, 'kind': kind, 'project_id': project['id'], 'project_name': project['name'],
                             'run_id': item['id'] if kind == 'extract' else run_id,
                             'completed': item.get('completed', item.get('page', 0)),
                             'created_at': item.get('created_at', ''),
                             'operation': item.get('operation', kind),
                             'status_path': path.relative_to(root).as_posix()})
    return sorted(jobs, key=lambda j: j['created_at'], reverse=True)


def cancel_job(store, queue, body):
    # Tra cứu từ danh sách thật thay vì nhận đường dẫn do trình duyệt gửi lên.
    job = next((j for j in list_jobs(store) if j['id'] == body.get('id') and j['project_id'] == body.get('project_id') and j['kind'] == body.get('kind')), None)
    if job is None:
        raise ValueError('Không tìm thấy tác vụ.')
    root = store.folder(job['project_id'])
    path = safe_path(root, job['status_path'])
    if job['kind'] == 'extract':
        return queue.cancel_extract(path.parent)
    if job['kind'] == 'ocr':
        raise ValueError('OCR panel đang chạy không thể dừng giữa lần infer.')
    if job['state'] in ('queued', 'running'):
        (path.parent/'cancel.requested').touch()
    return job
