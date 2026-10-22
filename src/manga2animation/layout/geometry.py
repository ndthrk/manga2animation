from math import floor, ceil


def pad_bbox(bbox, image_size, ratio=.1):
    """Nới mỗi phía theo tỷ lệ kích thước vùng gốc, không vượt ra ngoài ảnh."""
    x1, y1, x2, y2 = bbox
    dx, dy = (x2 - x1) * ratio, (y2 - y1) * ratio
    width, height = image_size
    return [max(0, floor(x1 - dx)), max(0, floor(y1 - dy)),
            min(width, ceil(x2 + dx)), min(height, ceil(y2 + dy))]


def area(b):
    """Tính diện tích khung; khung không hợp lệ có diện tích bằng 0."""
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def intersection(a, b):
    """Tính diện tích phần hai khung giao nhau."""
    return area((max(a[0], b[0]), max(a[1], b[1]),
                 min(a[2], b[2]), min(a[3], b[3])))


def reading_order(items, direction):
    """Sắp thứ tự bằng cách chia trang theo khoảng trống giữa các khung.

    Ưu tiên chia thành hàng, sau đó chia cột theo hướng đọc Nhật hoặc Việt.
    Nếu các khung chồng nhau và không có khoảng trống rõ, nhóm theo mép trên.
    Trang có bố cục chéo hoặc khung lồng nhau vẫn cần người dùng kiểm tra.
    """
    if len(items) < 2:
        return items[:]
    for axis in (1, 0):
        ordered = sorted(items, key=lambda item: item['bbox'][axis])
        groups = [[ordered[0]]]
        end = ordered[0]['bbox'][axis + 2]
        for item in ordered[1:]:
            if item['bbox'][axis] >= end:
                groups.append([])
            groups[-1].append(item)
            end = max(end, item['bbox'][axis + 2])
        if len(groups) > 1:
            if axis == 0 and direction == 'jp':
                groups.reverse()
            return [item for group in groups for item in reading_order(group, direction)]
    remaining = sorted(items, key=lambda item: item['bbox'][1])
    output = []
    while remaining:
        anchor = remaining[0]['bbox']
        tolerance = max(2, (anchor[3] - anchor[1]) * .2)
        row = [item for item in remaining if item['bbox'][1] <= anchor[1] + tolerance]
        row.sort(key=lambda item: item['bbox'][0], reverse=direction == 'jp')
        output.extend(row)
        remaining = [item for item in remaining if item not in row]
    return output


def filter_panels(panels, page_area, min_ratio, nested_ratio):
    """Bỏ khung quá nhỏ và khung nhỏ nằm gần như hoàn toàn trong khung lớn."""
    candidates = [p for p in panels if area(p['bbox']) / page_area >= min_ratio]
    return [p for p in candidates if not any(
        p is not other and area(p['bbox']) < area(other['bbox']) * nested_ratio
        and intersection(p['bbox'], other['bbox']) / area(p['bbox']) >= .95
        for other in candidates)]


