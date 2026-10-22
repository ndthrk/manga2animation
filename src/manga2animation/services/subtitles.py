"""Chia phụ đề theo cụm câu và âm tiết; xuất ASS có màu theo người nói."""
import math
import os
from pathlib import Path
import re
from functools import lru_cache
from .timing import dialogue_text

DEFAULTS = {'enabled': False, 'text_source': 'original', 'translation_language': 'vi',
            'max_words': 12, 'font': 'Arial', 'font_size': 32, 'position': 'bottom',
            'alignment': 'center', 'character_colors': True, 'color': '#ffffff', 'margin': 35}


def validate_subtitles(value):
    result={**DEFAULTS, **(value or {})}
    if result['text_source'] not in ('original','translation') or result['position'] not in ('top','middle','bottom') or result['alignment'] not in ('left','center','right'):
        raise ValueError('Nguồn hoặc vị trí phụ đề không hợp lệ.')
    for key,low,high in [('max_words',1,100),('font_size',8,160),('margin',0,500)]:
        if type(result[key]) is not int or not low<=result[key]<=high:
            raise ValueError(f'Phụ đề: {key} phải trong [{low}, {high}].')
    if not isinstance(result['font'],str) or not re.fullmatch(r'[^,\r\n{}\\]{1,100}',result['font']):
        raise ValueError('Tên font phụ đề không hợp lệ.')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',str(result['color'])):
        raise ValueError('Màu phụ đề phải có dạng #RRGGBB.')
    for key in ('enabled','character_colors'):
        if not isinstance(result[key],bool):
            raise ValueError('Bật phụ đề/màu nhân vật phải là boolean.')
    return result


@lru_cache(maxsize=1)
def fonts():
    """Đọc font có thật trên máy, gồm font hệ thống và font cài riêng của Windows."""
    from PIL import ImageFont
    roots=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts',
           Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Microsoft/Windows/Fonts',
           Path('/usr/share/fonts'),Path.home()/'.local/share/fonts']
    result={}
    for root in roots:
        if root.is_dir():
            for path in root.rglob('*'):
                if path.suffix.lower() not in ('.ttf','.otf','.ttc'):continue
                try:
                    family,style=ImageFont.truetype(str(path),12).getname()
                    normal=style.lower() in ('regular','normal','book','roman','plain')
                    if family not in result or normal and not result[family].get('normal'):
                        result[family]={'name':family,'path':str(path),'normal':normal}
                except (OSError,ValueError):continue
    return sorted(result.values(),key=lambda f:f['name'].lower())


def units(text):
    # Việt: đơn vị cách trắng gần với âm tiết; Nhật/Trung: từng chữ, không cắt giữa từ Latin.
    return list(re.finditer(r'[\u3040-\u30ff\u3400-\u9fff]|[^\s\u3040-\u30ff\u3400-\u9fff]+',text))


def split_caption(text, maximum):
    text=re.sub(r'\s+',' ',text).strip()
    tokens=units(text);chunks=[];start=0
    while start<len(tokens):
        end=min(start+maximum,len(tokens))
        if end<len(tokens):
            sentences=[i+1 for i in range(start,end) if re.search(r'[.!?。！？][”’"\')]*$',tokens[i].group())]
            boundaries=[i+1 for i in range(start,end) if re.search(r'[.!?。！？,;:，、；：][”’"\')]*$',tokens[i].group())]
            preferred=[i for i in boundaries if i-start>=max(1,maximum//2)]
            if sentences:end=sentences[-1]
            elif preferred:end=preferred[-1]
        left=tokens[start].start();right=tokens[end].start() if end<len(tokens) else len(text)
        chunks.append(text[left:right].strip());start=end
    return chunks


def syllables(text):
    # Đây là ước lượng nhịp đọc, không phải forced alignment theo từng âm vị.
    return max(1,len(units(text)))


def captions(panel, seconds, options, colors, intervals=None):
    options=validate_subtitles({**options,**panel.get('subtitle_settings',{})})
    if not options['enabled']:return []
    lines=[(line,dialogue_text(line,options['text_source'],options['translation_language'])) for line in panel['dialogues']]
    lines=[(line,text) for line,text in lines if text.strip()]
    if not lines:return []
    intervals=intervals or {}
    exact=all(line['id'] in intervals for line,_ in lines)
    weights=sum(syllables(text) for _,text in lines);cursor=0;result=[]
    for line,text in lines:
        if exact:
            begin,finish=intervals[line['id']]
        else:
            begin=cursor;finish=cursor+seconds*syllables(text)/weights;cursor=finish
        pieces=split_caption(text,options['max_words']);total=sum(syllables(p) for p in pieces)
        position=begin
        for piece in pieces:
            end=min(seconds,position+(finish-begin)*syllables(piece)/total)
            if round(end*100)>round(position*100):
                result.append({'start':round(position,2),'end':round(end,2),'text':piece,
                               'speaker_id':line['speaker_id'],'dialogue_id':line['id'],
                               'color':colors.get(line['speaker_id'],colors.get('unknown',options['color'])) if options['character_colors'] else options['color'],
                               'timing_source':'audio' if exact else 'estimated','settings':options})
            position=end
    return result


def ass_time(value):
    total=max(0,round(value*100));seconds,centiseconds=divmod(total,100);minutes,seconds=divmod(seconds,60);hours,minutes=divmod(minutes,60)
    return f'{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}'


def ass_color(value):
    return '&H'+value[5:7]+value[3:5]+value[1:3]+'&'


def write_ass(path, rows, width, height):
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,32,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,35,35,35,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events=[]
    for row in rows:
        cfg=row['settings'];align={'bottom':0,'middle':3,'top':6}[cfg['position']]+{'left':1,'center':2,'right':3}[cfg['alignment']]
        # Không cho nội dung OCR chèn lệnh ASS; giữ dấu câu và chữ Unicode.
        text=row['text'].replace('\\','＼').replace('{','｛').replace('}','｝').replace('\n',' ')
        tag='{'+f"\\an{align}\\fn{cfg['font']}\\fs{cfg['font_size']}\\c{ass_color(row['color'])}"+'}'
        margin=cfg['margin']
        events.append(f"Dialogue: 0,{ass_time(row['start'])},{ass_time(row['end'])},Default,,{margin},{margin},{margin},,{tag}{text}\n")
    Path(path).write_text(header+''.join(events),encoding='utf-8')
