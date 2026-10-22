import {useEffect,useState} from 'react';
import {SubtitleFields} from './SubtitleFields';
import {api} from './api';
import {LanguageSelect} from './LanguageSelect';
import {LLMFields} from './LLMFields';
import type {AudioSettings,Character,Language,Task,TimingSettings,TranslationSettings} from './types';

type Capabilities={ocr_languages:Record<string,Language[]>;translation_languages:Language[]};
let cached:Promise<Capabilities>|undefined;
export function useLanguages(){
  const [value,setValue]=useState<Capabilities>({ocr_languages:{paddleocr:[]},translation_languages:[]});
  useEffect(()=>{cached ||= api<Capabilities>('/capabilities');cached.then(setValue).catch(()=>{cached=undefined;});},[]);
  return value;
}
export function PaddleLanguage({value,onChange}:{value:string;onChange:(v:string)=>void}){
  const languages=useLanguages().ocr_languages.paddleocr;
  return <LanguageSelect label="Ngôn ngữ PaddleOCR" value={value} options={languages} onChange={onChange}/>;
}
export function TranslationFields({value,onChange,pull}:{value:TranslationSettings;onChange:(k:string,v:unknown)=>void;pull?:(settings:any)=>void}){
  const languages=useLanguages().translation_languages;
  return <><label>Provider dịch<select aria-label="Provider dịch" value={value.provider} onChange={e=>onChange('provider',e.target.value)}><option value="googletrans">Google Translate · googletrans</option><option value="ollama">Ollama local · LLM</option><option value="openai_compatible">API tương thích OpenAI · LLM</option></select></label>
    <LanguageSelect label="Ngôn ngữ nguồn dịch" value={value.source} onChange={v=>onChange('source',v)} options={languages} auto/>
    <LanguageSelect label="Ngôn ngữ đích dịch" value={value.target} onChange={v=>onChange('target',v)} options={languages}/>
    <label className="checkbox"><input type="checkbox" aria-label="Dịch nhiều ngôn ngữ" checked={!!value.targets?.length} onChange={e=>onChange('targets',e.target.checked?[value.target]:[])}/> Dịch đồng thời nhiều ngôn ngữ</label>{!!value.targets?.length&&<><div className="language-chips">{value.targets.map(code=><button key={code} onClick={()=>onChange('targets',value.targets!.filter(c=>c!==code))}>{code} ×</button>)}</div><LanguageSelect label="Thêm ngôn ngữ đích" value="" options={languages.filter(l=>!value.targets!.includes(l.code))} onChange={code=>onChange('targets',[...value.targets!,code])}/><small>Mỗi ngôn ngữ được lưu riêng, không ghi đè bản dịch ngôn ngữ khác.</small></>}
    <label>Số câu tối đa mỗi request<input aria-label="Số câu mỗi request dịch" type="number" min="1" max="100" value={value.batch_size} onChange={e=>onChange('batch_size',Number(e.target.value))}/></label><label>Giới hạn ký tự mỗi request<input aria-label="Ký tự mỗi request dịch" type="number" min="128" max="14000" value={value.max_chars_per_request} onChange={e=>onChange('max_chars_per_request',Number(e.target.value))}/><small>Câu trùng chỉ dịch một lần. Một câu dài được giữ riêng để không mất ranh giới bbox.</small></label>
    {value.provider==='googletrans'&&<label className="checkbox"><input aria-label="Gộp request Googletrans" type="checkbox" checked={value.batch_requests} onChange={e=>onChange('batch_requests',e.target.checked)}/> Gộp nhiều câu trong một request Google</label>}
    {value.provider!=='googletrans'&&<LLMFields provider={value.provider} value={value[value.provider as 'ollama'|'openai_compatible']} onChange={next=>onChange(value.provider,next)} pull={pull}/>}</>;
}
export function TimingFields({value,onChange}:{value:TimingSettings;onChange:(k:string,v:unknown)=>void}){
  return <><label>Cách tính thời lượng<select aria-label="Cách tính thời lượng" value={value.mode} onChange={e=>onChange('mode',e.target.value)}><option value="manual">Nhập số giây thủ công</option><option value="text">Theo độ dài văn bản</option><option value="audio">Theo âm thanh đã tạo</option></select></label>
    <label>Số giây tối thiểu<input aria-label="Số giây tối thiểu" type="number" min=".1" step=".1" value={value.min_seconds} onChange={e=>onChange('min_seconds',Math.max(.1,Number(e.target.value)))}/></label>
    <label>Tốc độ đọc (từ/phút)<input aria-label="Tốc độ đọc" type="number" min="1" value={value.words_per_minute} onChange={e=>onChange('words_per_minute',Math.max(1,Number(e.target.value)))}/></label>
    <label>Nguồn văn bản<select value={value.text_source} onChange={e=>onChange('text_source',e.target.value)}><option value="original">Lời thoại gốc</option><option value="translation">Bản dịch</option></select></label>
    {value.text_source==='translation'&&<LanguageSelect label="Bản dịch tính thời lượng" value={value.translation_language||'vi'} onChange={v=>onChange('translation_language',v)}/>}<label>Khoảng nghỉ giữa hai clip (giây)<input type="number" min="0" step=".1" value={value.dialogue_gap} onChange={e=>onChange('dialogue_gap',Math.max(0,Number(e.target.value)))}/></label>
    <p className="hint">Văn bản: tối thiểu + số từ × 60 / tốc độ đọc.<br/>Âm thanh: tối thiểu + tổng clip + khoảng nghỉ. Thiếu clip giữ thời lượng hiện có.</p></>;
}
export function AudioFields({value,onChange,advanced=false}:{value:AudioSettings;onChange:(k:string,v:unknown)=>void;advanced?:boolean}){
  return <><label>Đọc văn bản<select value={value.text_source} onChange={e=>onChange('text_source',e.target.value)}><option value="original">Lời thoại gốc</option><option value="translation">Bản dịch</option></select></label>
    <LanguageSelect label="Ngôn ngữ âm thanh" value={value.language} onChange={v=>onChange('language',v)}/>{value.text_source==='translation'&&<LanguageSelect label="Đọc bản dịch ngôn ngữ" value={value.translation_language||'vi'} onChange={v=>onChange('translation_language',v)}/>}
    <div className="field-pair"><label>Tốc độ giọng<input aria-label="Tốc độ giọng" type="number" min=".25" max="4" step=".05" value={value.speed} onChange={e=>onChange('speed',Math.min(4,Math.max(.25,Number(e.target.value))))}/></label><label>Số bước<input type="number" min="1" max="256" value={value.num_step} onChange={e=>onChange('num_step',Math.min(256,Math.max(1,Number(e.target.value))))}/></label></div>
    <div className="field-pair"><button onClick={()=>onChange('num_step',16)}>Nhanh · 16 bước</button><button onClick={()=>onChange('num_step',32)}>Chuẩn · 32 bước</button></div>
    {advanced&&<><label>Số câu mỗi lượt infer<input aria-label="Batch âm thanh" type="number" min="1" max="8" value={value.batch_size} onChange={e=>onChange('batch_size',Math.min(8,Math.max(1,Number(e.target.value))))}/><small>Máy 4 GB nên để 1. Nạp model một lần cho tác vụ, lưu riêng từng câu.</small></label>
      <label>Guidance scale<input type="number" min="0" step=".1" value={value.guidance_scale} onChange={e=>onChange('guidance_scale',Number(e.target.value))}/></label>
      <label className="checkbox"><input type="checkbox" checked={value.denoise} onChange={e=>onChange('denoise',e.target.checked)}/> Khử nhiễu theo prompt</label>
      <details><summary>Runtime OmniVoice riêng</summary><label>Giữ model trong RAM khi chờ (giây)<input aria-label="Giữ model âm thanh" type="number" min="0" max="300" value={value.omnivoice.keep_alive_seconds??60} onChange={e=>onChange('omnivoice',{...value.omnivoice,keep_alive_seconds:Number(e.target.value)})}/><small>GPU được giải phóng sau mỗi tác vụ. Đặt 0 nếu muốn giải phóng cả RAM ngay.</small></label>{['model','device','dtype','python_executable','python_path','asr_model','asr_device'].map(k=><label key={k}>{({model:'Thư mục checkpoint',device:'Thiết bị',dtype:'Kiểu số',python_executable:'Python thực thi (trống: Python trên máy)',python_path:'Thư mục thư viện riêng',asr_model:'Whisper local (tùy chọn)',asr_device:'Thiết bị Whisper'} as Record<string,string>)[k]}<input value={String(value.omnivoice[k as keyof typeof value.omnivoice]||'')} onChange={e=>onChange('omnivoice',{...value.omnivoice,[k]:e.target.value})}/></label>)}</details></>}
  </>;
}
export function GlobalServices({cfg,change,start,canRun}:{cfg:any;change:(path:string[],value:unknown)=>void;start:(operation:string,body?:Record<string,unknown>)=>void;canRun:boolean}){
  const [tab,setTab]=useState('translation');
  return <><nav className="service-tabs">{[['translation','Dịch'],['subtitles','Phụ đề'],['audio','Âm thanh'],['timing','Thời lượng']].map(([v,n])=><button className={tab===v?'active':''} key={v} onClick={()=>setTab(v)}>{n}</button>)}</nav><p className="hint">Thiết lập chung cho toàn bộ dự án. Panel có thể chọn ghi đè ở cột phải.</p>
    {tab==='translation'&&<><TranslationFields value={cfg.translation} onChange={(k,v)=>change(['translation',k],v)} pull={settings=>start('llm_pull',{settings})}/><button className="primary full" disabled={!canRun} onClick={()=>start('translate')}>Dịch toàn bộ hội thoại</button><p className="hint">Chỉ dịch khi bấm nút. Ollama chạy local; Google/API nhận văn bản theo provider bạn chọn. Không dịch tự động khi Extract.</p></>}
    {tab==='subtitles'&&<><h3>Phụ đề xuất video</h3><SubtitleFields value={cfg.video?.subtitles} onChange={(k,v)=>change(['video','subtitles',k],v)}/></>}
    {tab==='audio'&&<><AudioFields value={cfg.audio} onChange={(k,v)=>change(['audio',k],v)} advanced/><button className="primary full" disabled={!canRun} onClick={()=>start('audio',{reuse_existing:true})}>Tạo âm thanh còn thiếu / đã đổi</button><button className="full" disabled={!canRun} onClick={()=>start('audio')}>Tạo lại âm thanh toàn bộ</button><p className="hint">Chỉ chạy khi bấm nút này. Từng câu dùng giọng của người nói; người nói chưa có giọng được báo riêng.</p></>}
    {tab==='timing'&&<><TimingFields value={cfg.timing} onChange={(k,v)=>change(['timing',k],v)}/><p className="info-note">Đổi tốc độ chung sẽ tính lại các panel đang kế thừa. Panel cấu hình riêng giữ thiết lập riêng.</p></>}
  </>;
}

export function VoiceControls({character,asset,change,upload,start,disabled}:{character:Character;asset:(p:string)=>string;change:(voice:NonNullable<Character['voice']>)=>void;upload:(file:File)=>Promise<{path:string}>;start:(operation:string,body:Record<string,unknown>)=>void;disabled:boolean}){
  const [text,setText]=useState('Xin chào, đây là giọng nói của tôi.');
  const [error,setError]=useState('');
  const voice=character.voice||{};
  return <div className="voice-controls"><h4>Giọng nhân vật · OmniVoice</h4><label className="small-upload">Chọn âm thanh tham chiếu<input aria-label="Âm thanh tham chiếu" type="file" accept="audio/*" onChange={async e=>{const f=e.target.files?.[0];if(f)try{const result=await upload(f);change({reference_audio:result.path,reference_text:''});setError('');}catch(e){setError(String(e));}}}/></label>
    {voice.reference_audio&&<audio controls preload="none" src={asset(voice.reference_audio)}/>}
    <label>Bản chép lời âm thanh mẫu (tùy chọn)<textarea aria-label="Bản chép lời mẫu" value={voice.reference_text||''} onChange={e=>change({...voice,reference_text:e.target.value,prompt:undefined,preview:undefined})} placeholder="Để trống: tự nhận dạng khi bấm Lưu giọng. Có thể nhập hoặc sửa để chính xác hơn."/></label>
    <p className="hint">Âm thanh mẫu chính là giọng tham chiếu. “Lưu giọng” mã hóa mẫu thành prompt dùng lại, không huấn luyện model. Chỉ làm lại khi đổi mẫu; Generate dùng prompt đã lưu. Mẫu sạch 3–8 giây giúp giảm thời gian thử nghiệm.</p>
    <label>Văn bản nghe thử<textarea aria-label="Văn bản nghe thử" value={text} onChange={e=>setText(e.target.value)}/></label>
    <div className="field-pair"><button disabled={!voice.reference_audio||!text.trim()} onClick={()=>start('clone',{character_id:character.id,text})}>Lưu giọng & nghe thử</button><button disabled={!voice.prompt||!text.trim()} onClick={()=>start('preview',{character_id:character.id,text})}>Generate thử</button></div>
    {voice.preview&&<><span className="hint">Prompt giọng đã lưu · {voice.duration?.toFixed(2)}s</span><audio controls preload="none" src={asset(voice.preview)}/></>}{error&&<p className="inline-error">{error}</p>}
  </div>;
}

export function TaskStatus({task,onApply,onCancel,asset,onDismiss}:{task:Task|null;onApply:()=>void;onCancel:()=>void;asset:(p:string)=>string;onDismiss?:()=>void}){
  if(!task)return null;
  return <div role="status" data-task-id={task.id} className={'task-status task-'+task.state}><strong>{({llm_pull:'Tải model Ollama',translate:'Dịch hội thoại',audio:'Tạo âm thanh',clone:'Clone giọng',preview:'Nghe thử giọng'} as Record<string,string>)[task.operation]}</strong><span>{task.state} · {task.completed}/{task.total}</span>{!['queued','running'].includes(task.state)&&<button className="task-dismiss" title="Đóng thông báo tác vụ" onClick={onDismiss}>×</button>}
    {['queued','running'].includes(task.state)&&<button onClick={onCancel}>Dừng tác vụ</button>}
    {task.download_status&&<p>{task.download_status}{task.download_total?` · ${((task.download_completed||0)/1024**2).toFixed(0)} / ${(task.download_total/1024**2).toFixed(0)} MB`:''}</p>}{task.error&&<p>{task.error}</p>}{task.errors?.length?<p>{task.errors.length} câu có lỗi: {task.errors[0].error}</p>:null}
    {task.state==='completed'&&!task.applied_at&&<button className="primary" onClick={onApply}>Áp dụng kết quả</button>}
    {task.translation_requests!==undefined&&<p>{task.translation_requests} request · {task.deduplicated_sentences||0} câu trùng · {task.cached_sentences||0} câu cache{!!(task.input_tokens||task.output_tokens)&&` · ${task.input_tokens||0} token vào / ${task.output_tokens||0} token ra`}</p>}
    {task.reused_clips?<p>Đã dùng lại {task.reused_clips} clip còn khớp nội dung và giọng.</p>:null}
    {task.skipped?<p>{task.skipped} kết quả được giữ riêng vì nội dung/giọng đã thay đổi khi tác vụ đang chạy.</p>:null}
    {task.preview&&<audio controls preload="none" src={asset(task.preview)}/>}
  </div>;
}
