import {OCRLanguage} from './OCRLanguage';
import {SubtitleFields} from './SubtitleFields';
import {useState} from 'react';
import {LanguageSelect,useCatalog} from './LanguageSelect';
import {translationOf,setTranslation} from './translations';
import type React from 'react';
import {Info,Music2,Braces,MessageSquare,Settings2,GripVertical,Plus,X,ScanText,Trash2,RotateCcw,Languages} from 'lucide-react';
import type {Character,Dialogue,Edits,Panel,PanelEdit,Proposal} from './types';
import {AudioFields,PaddleLanguage,TimingFields,TranslationFields} from './ServiceSettings';
import {audioCurrent,defaultTiming} from './timing';

type Props={panel?:Panel;edit?:PanelEdit;cfg:any;characters:Character[];right:string;setRight:(v:string)=>void;
  change:(fn:(p:PanelEdit)=>void)=>void;start:(operation:string,body?:Record<string,unknown>)=>void;
  onDrag:(kind:string,id:string)=>(e:React.DragEvent)=>void;onDrop:(e:React.DragEvent,kind:string,id:string)=>void;
  asset:(p:string)=>string;engine:string;setEngine:(v:string)=>void;ocr:()=>void;proposal:Proposal|null;applyOCR:()=>void;clearOCR:()=>void;busy:boolean};
const engines=[['tesseract','Tesseract'],['indra','Indra ONNX'],['magi_v2','Magi v2'],['magi_v3','Magi v3'],['paddleocr','PaddleOCR']];

export function PanelInspector(p:Props){
  const {panel,edit,cfg,characters}=p;
  const [info,setInfo]=useState(false),[viewLanguage,setViewLanguage]=useState('');
  const catalog=useCatalog();
  const color=(id:string)=>characters.find(c=>c.id===id)?.color||characters.find(c=>c.id==='unknown')?.color||'#a5a5b8';
  const lineChange=(id:string,fn:(d:Dialogue)=>void)=>p.change(v=>fn(v.dialogues.find(d=>d.id===id)!));
  const task=(kind:string,line?:string)=>p.start(kind,{panel_ids:[panel!.id],...(kind==='translate'?{targets:[target]}:{}),...(line?{dialogue_ids:[line]}:{})});
  const translation={...cfg.translation,...edit?.translation_settings};
  const available=Array.from(new Set([translation.target,...(edit?.dialogues||[]).flatMap(d=>[...Object.keys(d.translations||{}),...(d.translation?[d.translation.target]:[])])])).filter(Boolean);
  const target=viewLanguage||translation.target;
  const current=(d:Dialogue)=>translationOf(d,target);
  const updateTranslation=(d:Dialogue,text:string)=>setTranslation(d,{...(current(d)||{source:translation.source,target,provider:translation.provider,input_text:d.text}),text,input_text:d.text});
  const languagePicker=<LanguageSelect label="Bản dịch đang xem / sửa" value={target} options={available.map(code=>({code,name:catalog.find(l=>l.code===code)?.name||code}))} onChange={setViewLanguage}/>;
  const audio={...cfg.audio,...edit?.audio_settings};
  const timing={...defaultTiming,...cfg.timing,...edit?.timing};
  return <aside className="right-pane"><div className="pane-heading"><span>THUỘC TÍNH PANEL</span><button className="icon-btn" title="Thông tin metadata panel" disabled={!panel} onClick={()=>setInfo(true)}><Info size={15}/></button></div>
    <nav className="tabs inspector-tabs">{[['dialogue','Hội thoại',<MessageSquare size={14}/>],['translation','Dịch',<Languages size={14}/>],['subtitles','Phụ đề',<MessageSquare size={14}/>],['settings','Thiết lập',<Settings2 size={14}/>],['audio','Âm thanh',<Music2 size={14}/>]].map(([id,name,icon])=><button key={String(id)} className={p.right===id?'active':''} onClick={()=>p.setRight(String(id))}>{icon}{name}</button>)}</nav>
    <div className="right-content">{panel&&edit?<>

      {p.right==='dialogue'&&<>{languagePicker}<div className="section-title"><h3>Hội thoại <em>{edit.dialogues.length}</em></h3><button className="icon-btn" title="Thêm lời thoại" onClick={()=>p.change(v=>v.dialogues.push({id:crypto.randomUUID(),text:'',speaker_id:'unknown'}))}><Plus size={17}/></button></div>
        {edit.dialogues.map((d,i)=><div className="dialogue-card" key={d.id} draggable onDragStart={p.onDrag('dialogue',d.id)} onDragOver={e=>e.preventDefault()} onDrop={e=>p.onDrop(e,'dialogue',d.id)}>
          <div className="dialogue-top"><GripVertical size={14}/><span className="line-number">{String(i+1).padStart(2,'0')}</span><select aria-label="Người nói" style={{color:color(d.speaker_id)}} value={d.speaker_id} onChange={e=>lineChange(d.id,v=>{v.speaker_id=e.target.value;})}>
            {!characters.some(c=>c.id===d.speaker_id)&&<option value={d.speaker_id}>● Unknown</option>}{d.speaker_id!=='unknown'&&!characters.some(c=>c.id==='unknown')&&<option value="unknown">● Unknown</option>}{characters.map(c=><option key={c.id} value={c.id} style={{color:c.color}}>● {c.name}</option>)}
          </select><button title="Xóa lời thoại" className="icon-btn" onClick={()=>p.change(v=>{v.dialogues=v.dialogues.filter(x=>x.id!==d.id);})}><X size={13}/></button></div>
          <textarea style={{color:color(d.speaker_id)}} aria-label="Nội dung lời thoại" value={d.text} placeholder="Nội dung lời thoại…" onChange={e=>lineChange(d.id,v=>{v.text=e.target.value;})}/>
          <div className="translation-row"><div className="line-tools"><span>Bản dịch {current(d)?`· ${current(d)!.target}`:''}</span>{current(d)?.input_text!==undefined&&current(d)!.input_text!==d.text&&<small>Nguồn đã đổi</small>}<button className="subtle" disabled={p.busy||!d.text.trim()} onClick={()=>task('translate',d.id)}>Dịch lại</button></div>
            <textarea style={{color:color(d.speaker_id)}} aria-label="Bản dịch lời thoại" placeholder="Chưa có bản dịch…" value={current(d)?.text||''} onChange={e=>lineChange(d.id,v=>{updateTranslation(v,e.target.value);})}/>
          </div><div className="line-tools"><button className="subtle" disabled={p.busy} onClick={()=>task('audio',d.id)}>Tạo lại âm thanh câu</button>{d.audio&&<span>{d.audio.duration.toFixed(2)}s {!audioCurrent(d,characters)?'· Nội dung/giọng đã đổi':''}</span>}</div>
          {d.audio&&<audio controls preload="none" src={p.asset(d.audio.path)}/>}
        </div>)}
        {!edit.dialogues.length&&<div className="mini-empty">Chưa có lời thoại.<br/>Thêm dòng mới hoặc mở tab Thiết lập để OCR riêng.</div>}<p className="hint">Kéo thẻ để đổi thứ tự. Bản dịch nằm ngay dưới từng câu gốc.</p>
      </>}
      {p.right==='translation'&&<>{languagePicker}<h3>Dịch riêng panel</h3><label className="checkbox"><input aria-label="Cấu hình dịch riêng" type="checkbox" checked={!!edit.translation_settings} onChange={e=>p.change(v=>{v.translation_settings=e.target.checked?{...cfg.translation}:undefined;})}/> Ghi đè cấu hình dịch chung</label>
        <fieldset disabled={!edit.translation_settings}><TranslationFields value={translation} onChange={(k,v)=>p.change(q=>{q.translation_settings={...translation,[k]:v};})}/></fieldset>
        <p className="hint">{edit.translation_settings?'Dùng thiết lập riêng ở trên.':'Đang kế thừa source/target từ cột trái.'} Không tự chia bản dịch thành mốc subtitle.</p>
        <button className="primary full" disabled={p.busy||!edit.dialogues.length} onClick={()=>task('translate')}>Dịch lại toàn panel</button>
        {edit.dialogues.map(d=><div className="translation-preview" style={{color:color(d.speaker_id)}} key={d.id}><p>{d.text}</p><textarea style={{color:color(d.speaker_id)}} aria-label="Bản dịch trong tab dịch" value={current(d)?.text||''} placeholder="Chưa dịch" onChange={e=>lineChange(d.id,v=>{updateTranslation(v,e.target.value);})}/><button className="subtle" disabled={p.busy} onClick={()=>task('translate',d.id)}>Dịch lại câu</button></div>)}
      </>}
      {p.right==='subtitles'&&<><h3>Phụ đề panel</h3><label className="checkbox"><input type="checkbox" checked={!!edit.subtitle_settings} onChange={e=>p.change(v=>{v.subtitle_settings=e.target.checked?{...cfg.video.subtitles}:undefined;})}/> Cấu hình phụ đề riêng</label><fieldset disabled={!edit.subtitle_settings}><SubtitleFields value={{...cfg.video?.subtitles,...edit.subtitle_settings}} onChange={(k,v)=>p.change(q=>{q.subtitle_settings={...cfg.video?.subtitles,...q.subtitle_settings,[k]:v};})}/></fieldset></>}
      {p.right==='audio' &&<><h3>Âm thanh panel</h3><div className="panel-settings"><h4>Âm thanh riêng</h4><label className="checkbox"><input type="checkbox" checked={!!edit.audio_settings} onChange={e=>p.change(v=>{v.audio_settings=e.target.checked?{...cfg.audio}:undefined;})}/> Ghi đè cấu hình giọng chung</label>
          <fieldset disabled={!edit.audio_settings}><AudioFields value={audio} onChange={(k,v)=>p.change(q=>{q.audio_settings={...audio,[k]:v};})}/></fieldset><button className="full" disabled={p.busy} onClick={()=>task('audio')}>Tạo lại âm thanh panel</button></div><p className="hint">Chọn ngôn ngữ bản dịch trước khi tạo. Cắt đầu/cuối và âm lượng chỉ áp dụng khi xuất video; tệp gốc luôn được giữ.</p>{edit.dialogues.map(d=><div className="dialogue-card" key={d.id}><strong style={{color:color(d.speaker_id)}}>{characters.find(c=>c.id===d.speaker_id)?.name||'Unknown'}</strong><p>{d.text}</p><button onClick={()=>task('audio',d.id)}>Tạo lại âm thanh câu</button>{d.audio&&<><audio controls preload="none" src={p.asset(d.audio.path)}/><small>{d.audio.text_source==='translation'?`Bản dịch ${d.audio.translation_language||'cũ'}`:'Lời thoại gốc'} · {d.audio.duration.toFixed(2)}s {!audioCurrent(d,characters)&&'· Nội dung/giọng đã đổi'}</small><div className="field-pair">{(['start','end'] as const).map(key=><label key={key}>{key==='start'?'Bắt đầu (giây)':'Kết thúc (giây)'}<input type="number" min="0" max={d.audio!.duration} step=".05" value={d.audio_edit?.[key]??(key==='start'?0:d.audio!.duration)} onChange={e=>lineChange(d.id,v=>{v.audio_edit={...v.audio_edit,[key]:Math.max(0,Math.min(d.audio!.duration,Number(e.target.value)))};})}/></label>)}</div><label>Âm lượng<input aria-label="Âm lượng câu" type="range" min="0" max="2" step=".05" value={d.audio_edit?.volume??1} onChange={e=>lineChange(d.id,v=>{v.audio_edit={...v.audio_edit,volume:Number(e.target.value)};})}/></label><label className="checkbox"><input type="checkbox" checked={!!d.audio_edit?.muted} onChange={e=>lineChange(d.id,v=>{v.audio_edit={...v.audio_edit,muted:e.target.checked};})}/> Tắt tiếng câu này khi xuất</label></>}</div>)}</>}
      {p.right==='settings'&&<><h3>Thiết lập panel</h3><label>Thời lượng phát<input aria-label="Thời lượng panel" type="number" min=".1" step=".1" value={edit.duration} onChange={e=>p.change(v=>{v.duration=Math.max(.1,Number(e.target.value));v.timing={...v.timing,mode:'manual'};})}/><small>giây · {edit.duration_source==='audio_pending'?'Chưa đủ clip, giữ thời lượng hiện có':edit.duration_source||'manual'}</small></label>
        <label className="checkbox"><input type="checkbox" checked={!!edit.timing} onChange={e=>p.change(v=>{v.timing=e.target.checked?{...cfg.timing}:undefined;})}/> Thời lượng riêng cho panel</label><fieldset disabled={!edit.timing}><TimingFields value={timing} onChange={(k,v)=>p.change(q=>{q.timing={...timing,[k]:v};})}/></fieldset>
        <div className="panel-settings"><h4>OCR riêng</h4><label>Engine OCR lại<select aria-label="Engine OCR lại" value={p.engine} onChange={e=>p.setEngine(e.target.value)}>{engines.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
          <OCRLanguage engine={p.engine} value={edit.ocr_settings?.languages?.[p.engine]||edit.ocr_settings?.language||cfg.ocr?.[p.engine]?.language||'vi'} onChange={language=>p.change(v=>{v.ocr_settings={...v.ocr_settings,languages:{...v.ocr_settings?.languages,[p.engine]:language}};})}/>
          <button className="full" disabled={!!p.proposal&&['queued','running'].includes(p.proposal.state)} onClick={p.ocr}><ScanText size={15}/> OCR riêng panel</button>
          {p.proposal&&p.proposal.panel_id===panel.id&&<div className="proposal"><strong>Kết quả OCR đề xuất</strong>{p.proposal.state==='completed'?<>{p.proposal.dialogues?.map(d=><p key={d.id}>{d.text||'(trống)'}</p>)}<button className="primary" onClick={p.applyOCR}>Áp dụng kết quả</button><button className="subtle" onClick={p.clearOCR}>Bỏ qua</button></>:<p>{p.proposal.state==='failed'?p.proposal.error:'Đang xử lý trong hàng đợi…'}</p>}</div>}
        </div>
        <button className="danger subtle" onClick={()=>p.change(v=>{v.hidden=!v.hidden;})}>{edit.hidden?<RotateCcw size={14}/>:<Trash2 size={14}/>} {edit.hidden?'Khôi phục panel':'Ẩn panel khỏi timeline'}</button>
      </>}
    </>:<div className="mini-empty"><MessageSquare size={28}/><p>Chọn một panel trên timeline để xem và sửa nội dung.</p></div>}</div>
    {info&&panel&&<div className="modal-backdrop"><section className="modal metadata-dialog" role="dialog" aria-label="Metadata panel"><div className="section-title"><h3>Thông tin trích xuất gốc</h3><button title="Đóng metadata" onClick={()=>setInfo(false)}><X size={17}/></button></div><p className="hint">Tọa độ trang gốc, upscale và panel · chỉ đọc.</p><pre className="code metadata">{JSON.stringify(panel,null,2)}</pre></section></div>}
  </aside>;
}
