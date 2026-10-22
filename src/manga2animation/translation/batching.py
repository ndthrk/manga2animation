"""Chia theo số câu và ngân sách ký tự, không cắt đôi nội dung một bbox."""
def pack_items(items, max_items=16, max_chars=4000, text_key='input_text'):
    chunk, length = [], 0
    for item in items:
        size = len(item[text_key])+16
        if chunk and (len(chunk)>=max_items or length+size>max_chars):
            yield chunk
            chunk, length = [], 0
        chunk.append(item)
        length += size
    if chunk:
        yield chunk
