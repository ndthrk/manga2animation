"""Gộp câu bằng dấu phân cách có ID, cache từng câu và giữ đúng ranh giới bbox."""
import asyncio
import json
import sqlite3
import time
import re
from pathlib import Path
from contextlib import closing
from ..settings import ROOT
from .batching import pack_items


def split_google_batch(text, count):
    matches = list(re.finditer(r'⟦\s*(\d+)\s*⟧', text))
    if len(matches) != count or {int(m.group(1)) for m in matches} != set(range(count)):
        raise ValueError('Google làm thay đổi dấu phân cách batch.')
    if text[:matches[0].start()].strip():
        raise ValueError('Google thêm nội dung ngoài batch.')
    result = {}
    for index, match in enumerate(matches):
        end = matches[index+1].start() if index+1<count else len(text)
        value = ' '.join(text[match.end():end].split())
        if not value:
            raise ValueError('Google trả một câu trống trong batch.')
        result[int(match.group(1))] = value
    return [result[i] for i in range(count)]


class GoogleTranslationProvider:
    blocked_until = 0

    def __init__(self, timeout_seconds=30, request_interval=1.0, retries=2, cache_path=None,
                 batch_requests=True, max_chars_per_request=4000):
        self.timeout = timeout_seconds
        self.interval, self.retries = max(0, request_interval), max(0, retries)
        self.cache_path = Path(cache_path or ROOT/'.cache/translations.sqlite3')
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_requests, self.max_chars = batch_requests, max_chars_per_request
        self.request_count = self.cached_count = self.sent_characters = 0

    def translate(self, texts, source='auto', target='vi'):
        try:
            from googletrans import Translator
        except ImportError as exc:
            raise RuntimeError('Chưa có googletrans. Chạy: python -m pip install -r requirements-translation.txt') from exc
        import httpx
        async def work(database):
            output, pending = {}, []
            for text in dict.fromkeys(texts):
                key = json.dumps([source,target,text],ensure_ascii=False)
                row = database.execute('SELECT value FROM translations WHERE key=?',(key,)).fetchone()
                if row:
                    output[text] = {**json.loads(row[0]),'cached':True}
                    self.cached_count += 1
                elif source == target:
                    output[text] = {'text':text,'source':source,'target':target}
                else:
                    pending.append({'input_text':text,'key':key})
            if not pending:
                return [output[text] for text in texts]
            async with Translator(service_urls=['translate.googleapis.com'], raise_exception=True,
                                  timeout=httpx.Timeout(self.timeout), list_operation_max_concurrency=1) as client:
                async def request(content):
                    if time.time()<type(self).blocked_until:
                        raise RuntimeError('Google đang giới hạn lượt dịch (429). Hãy đợi khoảng một phút rồi thử lại.')
                    for attempt in range(self.retries+1):
                        try:
                            self.request_count += 1
                            self.sent_characters += len(content)
                            result = await asyncio.wait_for(client.translate(content,src=source,dest=target),self.timeout)
                            await asyncio.sleep(self.interval)
                            return result
                        except Exception as exc:
                            limited = '429' in str(exc)
                            if attempt < self.retries:
                                response = getattr(exc, 'response', None)
                                try:
                                    delay = min(60, max(2**(attempt+1), float(response.headers.get('Retry-After', 0)))) if response is not None else 2**(attempt+1)
                                except (TypeError, ValueError):
                                    delay = 2**(attempt+1)
                                await asyncio.sleep(delay)
                                continue
                            if limited:
                                type(self).blocked_until = time.time()+60
                            raise RuntimeError('Google đang giới hạn lượt dịch (429). Hãy đợi khoảng một phút rồi thử lại.' if limited else 'Không dịch được batch: '+str(exc)) from exc
                def store(entry, value, result):
                    item = {'text':value,'source':result.src,'target':result.dest}
                    output[entry['input_text']] = item
                    database.execute('INSERT OR REPLACE INTO translations VALUES (?,?)',(entry['key'],json.dumps(item,ensure_ascii=False)))
                    database.commit()
                for chunk in pack_items(pending,100 if self.batch_requests else 1,self.max_chars):
                    content = chunk[0]['input_text'] if len(chunk)==1 else '\n'.join(f"⟦{i}⟧\n{item['input_text']}" for i,item in enumerate(chunk))
                    try:
                        if len(content)>14000:
                            raise ValueError('Một vùng chữ quá dài cho Googletrans; hãy chia bbox hoặc sửa nội dung trước.')
                        result = await request(content)
                        if len(chunk)==1:
                            translated = [result.text]
                        else:
                            try:
                                translated = split_google_batch(result.text,len(chunk))
                            except ValueError:
                                # Chỉ tách riêng khi dấu phân cách bị đổi; không làm vậy khi gặp 429.
                                for entry in chunk:
                                    try:
                                        single = await request(entry['input_text'])
                                        store(entry,single.text,single)
                                    except Exception as exc:
                                        output[entry['input_text']] = {'error':str(exc)}
                                continue
                        for entry,value in zip(chunk,translated):
                            store(entry,value,result)
                    except Exception as exc:
                        for entry in chunk:
                            output[entry['input_text']] = {'error':str(exc)}
            return [output[text] for text in texts]
        with closing(sqlite3.connect(self.cache_path)) as database:
            database.execute('CREATE TABLE IF NOT EXISTS translations (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            return asyncio.run(work(database))


def language_list():
    try:
        from googletrans import LANGUAGES
        return [{'code': code, 'name': name} for code, name in sorted(LANGUAGES.items())]
    except ImportError:
        return [{'code': c, 'name': n} for c, n in [('vi','Tiếng Việt'), ('en','English'), ('ja','日本語'),
                 ('ko','한국어'), ('zh-cn','中文 giản thể'), ('zh-tw','中文 phồn thể'), ('fr','Français'), ('de','Deutsch'), ('th','ไทย')]]
