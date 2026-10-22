"""Hủy hợp tác giữa các lượt infer, không ép ngắt kernel đang dùng GPU."""


class ExtractionCancelled(Exception):
    pass


def check_cancel(folder):
    if (folder / 'cancel.requested').exists():
        raise ExtractionCancelled('Đã dừng trích xuất theo yêu cầu.')
