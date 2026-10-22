import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {parse, stringify} from 'yaml';
import {Layers, Plus, Upload, Settings2, Users, MessageSquare, Image as ImageIcon, Save, Play, Trash2, RotateCcw, ZoomIn, ZoomOut, ScanText, GripVertical, X, Music2, ChevronLeft, ChevronRight, FolderOpen, Eye, EyeOff, Sparkles, Braces} from 'lucide-react';
import type {Project, Edits, Manifest, Status, Proposal, Panel} from './types';
import './style.css';

import {api} from './api';
import {GlobalServices,PaddleLanguage,VoiceControls,TaskStatus} from './ServiceSettings';
import {PageEditor} from './PageEditor';
import {OCRLanguage} from './OCRLanguage';
import {JobsDialog,type Job} from './JobsDialog';
import {ResizeHandle} from './ResizeHandle';
import {CharacterReference} from './CharacterReference';
import {VideoDialog} from './VideoDialog';
import {PanelInspector} from './PanelInspector';
import {recalculate} from './timing';
import {mergeServer} from './merge';
import type {Task,ExtractPlan} from './types';
const engines=[['tesseract','Tesseract'],['indra','Indra ONNX'],['magi_v2','Magi v2'],['magi_v3','Magi v3'],['paddleocr','PaddleOCR']];
const stageNames:Record<string,string>={reuse:'Dùng lại kết quả trang cũ',cancelled:'Đã dừng',cancelling:'Đang dừng sau bước hiện tại',queued:'Đang chờ',upscale:'Nâng cấp ảnh',load_magi:'Đang nạp Magi v2',detection:'Phân tích bố cục',identity:'Đối chiếu nhân vật',layout:'Cắt & sắp xếp panel',ocr:'Nhận dạng chữ',completed:'Hoàn tất',failed:'Có lỗi',interrupted:'Đã gián đoạn'};

function App(){
  const [projects,setProjects]=useState<Project[]>([]),[project,setProject]=useState<Project|null>(null);
  const [config,setConfig]=useState(''),[runs,setRuns]=useState<Status[]>([]),[runId,setRunId]=useState('');
  const [manifest,setManifest]=useState<Manifest|null>(null),[edits,setEdits]=useState<Edits|null>(null),[selected,setSelected]=useState('');
  const [status,setStatus]=useState<Status|null>(null),[left,setLeft]=useState('images'),[right,setRight]=useState('dialogue');
  const [deleted,setDeleted]=useState(false),[showImages,setShowImages]=useState(true),[textBoxes,setTextBoxes]=useState(true),[charBoxes,setCharBoxes]=useState(false),[zoom,setZoom]=useState(1);
  const [error,setError]=useState(''),[saveState,setSaveState]=useState('Đã lưu'),[proposal,setProposal]=useState<Proposal|null>(null),[ocrEngine,setOcrEngine]=useState('tesseract');
  const [task,setTask]=useState<Task|null>(null);
  const [extractMode,setExtractMode]=useState<'incremental'|'full'>('incremental');
  const [selectedPage,setSelectedPage]=useState('');
  const [videoOpen,setVideoOpen]=useState(false),[jobsOpen,setJobsOpen]=useState(false);
  const [jobCount,setJobCount]=useState(0);
  useEffect(()=>{const poll=()=>api<Job[]>('/jobs').then(items=>setJobCount(items.filter(j=>['queued','running','cancelling'].includes(j.state)).length)).catch(()=>{});poll();const timer=setInterval(poll,2000);return()=>clearInterval(timer);},[]);
  const [extractPlan,setExtractPlan]=useState<ExtractPlan|null>(null);
  const autoApply=useRef('');
  const [newName,setNewName]=useState(''),[creating,setCreating]=useState(false),[busy,setBusy]=useState(false);
  const dirty=useRef({project:false,config:false,edits:false}), latest=useRef({project,config,edits,runId}), saving=useRef<Promise<void>|null>(null);
  const generation=useRef(0), drag=useRef<{kind:string;id:string}|null>(null);
  latest.current={project,config,edits,runId};
  const base=project?`/projects/${project.id}`:'';
  const panels=manifest?.pages.flatMap(p=>p.panels)||[];
  const panel=panels.find(p=>p.id===selected), panelEdit=edits?.panels[selected];
  const batch=edits?.batches.find(b=>b.id===panelEdit?.batch_id);
  const characters=project?.characters||[];
  const unknown=project?.unknown_character||{id:'unknown',name:'Unknown',color:'#a5a5b8'};
  const speakers=[...characters,unknown];
  const speakerName=(id:string)=>characters.find(c=>c.id===id)?.name||'Unknown';
  const speakerColor=(id:string)=>speakers.find(c=>c.id===id)?.color||unknown.color;
  const asset=(path:string)=>`/api${base}/artifacts/${path}`;
  const panelAsset=(p:Panel)=>asset(`extracts/${runId}/${p.image}`);
  const fail=(e:unknown)=>setError(e instanceof Error?e.message:String(e));
  const mutateProject=(fn:(p:Project)=>void)=>{if(!latest.current.project)return;const p=structuredClone(latest.current.project);fn(p);dirty.current.project=true;latest.current.project=p;setProject(p);setSaveState('Chưa lưu');};
  const mutateEdits=(fn:(e:Edits)=>void)=>{if(!latest.current.edits)return;const e=structuredClone(latest.current.edits);fn(e);recalculate(e,parse(latest.current.config)?.timing||{},(latest.current.project?[...latest.current.project.characters,...(latest.current.project.unknown_character?[latest.current.project.unknown_character]:[])]:undefined));e.order.sort((a,b)=>e.batches.findIndex(x=>x.id===e.panels[a].batch_id)-e.batches.findIndex(x=>x.id===e.panels[b].batch_id));dirty.current.edits=true;latest.current.edits=e;setEdits(e);setSaveState('Chưa lưu');};
  const editPanel=(fn:(p:NonNullable<typeof panelEdit>)=>void)=>mutateEdits(e=>fn(e.panels[selected]));
  const configChange=(text:string)=>{
    dirty.current.config=true;setConfig(text);setSaveState('Chưa lưu');
    if(edits)try{const next=structuredClone(edits);recalculate(next,parse(text)?.timing||{},(latest.current.project?[...latest.current.project.characters,...(latest.current.project.unknown_character?[latest.current.project.unknown_character]:[])]:undefined));dirty.current.edits=true;setEdits(next);}catch{/* Chờ YAML hoàn chỉnh trước khi tính lại. */}
  };
  const setOption=(path:string[],value:unknown)=>{try{const c=parse(config);let node=c;for(const key of path.slice(0,-1))node=node[key] ||= {};node[path.at(-1)!]=value;configChange(stringify(c));}catch(e){fail(e);}};
  let cfg:any={};try{cfg=parse(config)||{};}catch{/* YAML chưa hoàn chỉnh vẫn được giữ trong ô nhập. */}

  async function save():Promise<void>{
    if(saving.current){await saving.current; if(Object.values(dirty.current).some(Boolean))return save(); return;}
    const task=(async()=>{
      const captured=latest.current, flags={...dirty.current};
      if(!captured.project||!Object.values(flags).some(Boolean))return;
      dirty.current={project:false,config:false,edits:false};setSaveState('Đang lưu…');
      const prefix=`/projects/${captured.project.id}`;
      try{
        if(flags.config)await api(prefix+'/config','PUT',{text:captured.config});
        if(flags.project){const saved=await api<Project>(prefix,'PUT',captured.project);if(latest.current.project?.id===saved.id){const next={...latest.current.project,revision:saved.revision};latest.current.project=next;setProject(next);}}
        if(flags.edits&&captured.edits&&captured.runId){const saved=await api<Edits>(prefix+`/extracts/${captured.runId}/edits`,'PUT',captured.edits);if(latest.current.runId===captured.runId&&latest.current.edits){const next={...latest.current.edits,revision:saved.revision};latest.current.edits=next;setEdits(next);}}
        setSaveState(Object.values(dirty.current).some(Boolean)?'Chưa lưu':'Đã lưu');
      }catch(e){for(const k of Object.keys(flags) as (keyof typeof flags)[])dirty.current[k] ||= flags[k];setSaveState('Lưu thất bại');throw e;}
    })();saving.current=task;try{await task;}finally{saving.current=null;}
  }
  useEffect(()=>{api<Project[]>('/projects').then(setProjects).catch(fail);},[]);
  useEffect(()=>{
    if(!project){setExtractPlan(null);return;}
    let ignored=false;
    setExtractPlan(null);
    const timer=setTimeout(()=>api<ExtractPlan>(base+'/extract-plan','POST',{mode:extractMode,base_run_id:runId||null,config_text:config})
      .then(value=>{if(!ignored)setExtractPlan(value);}).catch(()=>{if(!ignored)setExtractPlan(null);}),1200);
    return()=>{ignored=true;clearTimeout(timer);};
  },[project?.id,project?.revision,config,runId,extractMode,status?.state]);
  useEffect(()=>{if(!Object.values(dirty.current).some(Boolean))return;const timer=setTimeout(()=>save().catch(fail),900);return()=>clearTimeout(timer);},[project,config,edits]);
  useEffect(()=>{const handler=(e:BeforeUnloadEvent)=>{if(Object.values(dirty.current).some(Boolean)){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[]);

  async function selectProject(id:string){
    await save();const gen=++generation.current;
    const [p,c,r]=await Promise.all([api<Project>(`/projects/${id}`),api<{text:string}>(`/projects/${id}/config`),api<Status[]>(`/projects/${id}/extracts`)]);
    if(gen!==generation.current)return;
    setSelectedPage('');setProject(p);setConfig(c.text);setRuns(r);setRunId('');setManifest(null);setEdits(null);setStatus(null);setProposal(null);setSelected('');setTask(null);setExtractMode('incremental');dirty.current={project:false,config:false,edits:false};
    const completed=r.find(s=>['queued','running','cancelling'].includes(s.state))||r.find(s=>s.state==='completed');if(completed)await openRun(completed.id,id);
  }
  async function openRun(id:string,pid=project?.id){
    if(!pid)return;await save();
    const result=await api<{status:Status;manifest:Manifest|null;edits:Edits|null}>(`/projects/${pid}/extracts/${id}`);
    setSelectedPage('');setRunId(id);setManifest(result.manifest);setEdits(result.edits);setStatus(result.status);setProposal(null);setSelected(result.edits?.order[0]||'');setZoom(1);
  }
  useEffect(()=>{
    if(!project||!runId||!status||!['queued','running','cancelling'].includes(status.state))return;
    const timer=setInterval(async()=>{try{const r=await api<{status:Status;manifest:Manifest|null;edits:Edits|null}>(base+`/extracts/${runId}`);setStatus(r.status);if(r.status.state==='completed'){setManifest(r.manifest);setEdits(r.edits);setSelected(r.edits?.order[0]||'');setRuns(await api(base+'/extracts'));}if(r.status.state==='failed')setError(r.status.error||'Extract thất bại');}catch(e){fail(e);}},1000);
    return()=>clearInterval(timer);
  },[project?.id,runId,status?.state]);
  useEffect(()=>{
    if(!proposal||!['queued','running'].includes(proposal.state))return;
    const timer=setInterval(()=>api<Proposal>(base+`/extracts/${runId}/proposals/${proposal.id}`).then(setProposal).catch(fail),1000);
    return()=>clearInterval(timer);
  },[proposal?.id,proposal?.state,base,runId]);
  async function createProject(){const p=await api<Project>('/projects','POST',{name:newName});setProjects(await api('/projects'));setCreating(false);setNewName('');await selectProject(p.id);}
  async function upload(files:FileList|null,reference=false){if(!files?.length||!project)return;await save();const form=new FormData();Array.from(files).forEach(f=>form.append('files',f));setBusy(true);try{const result=await api<{image:string}[]>(base+`/uploads?reference=${reference}`,'POST',form);if(reference)return result[0];setProject(await api(base));}finally{setBusy(false);}}
  async function start(){
    const pid=project?.id,mode=extractMode,baseline=runId||null;
    if(!pid)return;
    setBusy(true);
    try{
      await save();
      const plan=await api<ExtractPlan>(base+'/extract-plan','POST',{mode,base_run_id:baseline});
      if(latest.current.project?.id!==pid)return;
      setExtractPlan(plan);
      const summary=mode==='full'?'Trích xuất lại toàn bộ và tạo timeline mới.':`Bổ sung trang: dùng lại ${plan.reused_pages} trang, xử lý ${plan.processing_pages} trang.`;
      if(!window.confirm(summary+'\nTạo một lần Extract mới với cấu hình hiện tại?'))return;
      setSelectedPage('');
      const run=await api<Status>(base+'/extracts','POST',{mode,base_run_id:baseline});
      setRuns(await api(base+'/extracts'));setRunId(run.id);setStatus(run);setManifest(null);setEdits(null);setSelected('');setProposal(null);
    }finally{setBusy(false);}
  }
  const taskBusy=false; // Có thể gửi thêm tác vụ khi hàng đợi đang xử lý.
  async function startTask(operation:string,body:Record<string,unknown>={}){
    try{await save();const created=await api<Task>(base+'/tasks','POST',{operation,run_id:runId||undefined,...body});autoApply.current='';setTask(created);}catch(e){fail(e);}
  }
  async function applyTask(current=task){
    if(!current)return;
    const ownerId=project?.id;
    if(!ownerId||latest.current.project?.id!==ownerId)return;
    try{
      await save();
      if(latest.current.project?.id!==ownerId)return;
      const beforeProject=structuredClone(latest.current.project!);
      const beforeEdits=latest.current.edits?structuredClone(latest.current.edits):null;
      const result=await api<{task:Task;project:Project;edits:Edits|null}>(base+`/tasks/${current.id}/apply`,'POST',{revision:latest.current.edits?.revision,project_revision:latest.current.project?.revision});
      if(latest.current.project?.id!==ownerId)return;
      setTask(result.task);
      const nextProject=dirty.current.project?mergeServer(beforeProject,latest.current.project!,result.project):result.project;
      latest.current.project=nextProject;setProject(nextProject);
      if(result.edits&&latest.current.runId===current.run_id){
        const next=dirty.current.edits&&beforeEdits?mergeServer(beforeEdits,latest.current.edits!,result.edits):result.edits;
        latest.current.edits=next;setEdits(next);
      }
      if(current.operation==='clone'&&latest.current.edits){const next=recalculate(structuredClone(latest.current.edits),cfg.timing,[...nextProject.characters,...(nextProject.unknown_character?[nextProject.unknown_character]:[])]);dirty.current.edits=true;latest.current.edits=next;setEdits(next);}
    }catch(e){fail(e);}
  }
  // Theo dõi mọi tác vụ của lần Extract, không bỏ quên tác vụ trước khi gửi thêm.
  const polling=useRef(false);
  useEffect(()=>{
    if(!project)return;
    let stopped=false;
    const poll=async()=>{
      if(polling.current)return;polling.current=true;
      try{
        const items=await api<Task[]>(base+'/tasks');
        if(stopped)return;
        const pending=items.filter(t=>(!t.run_id||t.run_id===latest.current.runId)&&t.state==='completed'&&!t.applied_at).reverse();
        for(const item of pending){if(stopped)break;if(autoApply.current!==item.id){autoApply.current=item.id;await applyTask(item);}}
        const active=items.find(t=>(!t.run_id||t.run_id===latest.current.runId)&&['queued','running'].includes(t.state));
        if(!stopped)setTask(previous=>active||(previous?items.find(t=>t.id===previous.id)||previous:null));
      }catch(e){if(!stopped)fail(e);}finally{polling.current=false;}
    };
    poll();const timer=setInterval(poll,1200);return()=>{stopped=true;clearInterval(timer);};
  },[project?.id,runId]);
  async function uploadVoice(file:File){await save();const form=new FormData();form.append('file',file);return api<{path:string}>(base+'/voice-uploads','POST',form);}
  async function deleteProject(){
    if(!project||!window.confirm(`Xóa project “${project.name}”? Dữ liệu sẽ được chuyển vào thùng rác cục bộ.`))return;
    try{await save();await api(base,'DELETE');dirty.current={project:false,config:false,edits:false};latest.current={project:null,config:'',edits:null,runId:''};setProject(null);setEdits(null);setManifest(null);setRunId('');setStatus(null);setTask(null);setProjects(await api('/projects'));}catch(e){fail(e);}
  }
  async function deleteRun(){
    if(!runId||!window.confirm('Xóa lần Extract đang chọn và chuyển dữ liệu vào thùng rác cục bộ?'))return;
    try{await save();await api(base+`/extracts/${runId}`,'DELETE');setRunId('');setEdits(null);setManifest(null);setStatus(null);setSelected('');setTask(null);setRuns(await api(base+'/extracts'));}catch(e){fail(e);}
  }
  async function reOCR(){try{await save();setProposal(await api(base+`/extracts/${runId}/ocr`,'POST',{panel_id:selected,engine:ocrEngine,language:panelEdit?.ocr_settings?.languages?.[ocrEngine]||panelEdit?.ocr_settings?.language||cfg.ocr?.[ocrEngine]?.language}));}catch(e){fail(e);}}
  async function applyOCR(){try{await save();setEdits(await api(base+`/extracts/${runId}/proposals/${proposal!.id}/apply`,'POST',{revision:latest.current.edits?.revision}));setProposal(null);}catch(e){fail(e);}}
  function reorder(kind:string,id:string,target:string){
    if(id===target)return;
    if(kind==='panel')mutateEdits(e=>{e.order=e.order.filter(i=>i!==id);e.order.splice(e.order.indexOf(target),0,id);e.panels[id].batch_id=e.panels[target].batch_id;});
    if(kind==='page')mutateProject(p=>{const item=p.pages.find(x=>x.id===id)!;p.pages=p.pages.filter(x=>x.id!==id);p.pages.splice(p.pages.findIndex(x=>x.id===target),0,item);});
    if(kind==='dialogue')editPanel(p=>{const d=p.dialogues.find(d=>d.id===id)!;p.dialogues=p.dialogues.filter(d=>d.id!==id);p.dialogues.splice(p.dialogues.findIndex(d=>d.id===target),0,d);});
  }
  function drop(e:React.DragEvent,kind:string,id:string){e.preventDefault();if(drag.current?.kind===kind)reorder(kind,drag.current.id,id);drag.current=null;}
  const startDrag=(kind:string,id:string)=>(e:React.DragEvent)=>{drag.current={kind,id};e.dataTransfer.setData('text/plain',id);e.dataTransfer.effectAllowed='move';};
  function moveBoundary(index:number,delta:number){mutateEdits(e=>{const a=e.batches[index],b=e.batches[index+1];const left=e.order.filter(id=>!e.panels[id].hidden&&e.panels[id].batch_id===a.id),right=e.order.filter(id=>!e.panels[id].hidden&&e.panels[id].batch_id===b.id);if(delta<0&&left.length)e.panels[left.at(-1)!].batch_id=b.id;if(delta>0&&right.length)e.panels[right[0]].batch_id=a.id;});}
  const totalDuration=edits?edits.order.reduce((n,id)=>n+(edits.panels[id].hidden?0:edits.panels[id].duration),0):0;
  const button=(icon:React.ReactNode,label:string,action:()=>void,active=false)=><button title={label} className={'icon-btn '+(active?'active':'')} onClick={action}>{icon}</button>;

  return <div className="app">
    <header><div className="brand"><div className="brand-mark"><Layers size={21}/></div><span>Manga<span className="brand-light">2</span>Animation<small>LOCAL STUDIO</small></span></div>
      <div className="project-select"><FolderOpen size={16}/><select aria-label="Chọn project" value={project?.id||''} onChange={e=>selectProject(e.target.value).catch(fail)}><option value="" disabled>Chọn project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.id===project?.id?project.name:p.name}</option>)}</select><button className="icon-btn" title="Tạo project" onClick={()=>setCreating(true)}><Plus size={17}/></button></div>
      <div className="run-select"><span>LẦN TRÍCH XUẤT</span><select aria-label="Chọn extract" value={runId} onChange={e=>openRun(e.target.value).catch(fail)}><option value="">Chưa trích xuất</option>{runs.map(r=><option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString('vi-VN')} · {r.id.slice(0,6)} · {stageNames[r.state]||r.state}</option>)}</select></div>
      <div className="header-end">{project&&<button disabled={!edits} onClick={()=>setVideoOpen(true)}><Play size={15}/> Tạo video</button>}<button onClick={()=>setJobsOpen(true)}>Tác vụ {jobCount>0&&<em>{jobCount}</em>}</button>{project&&<details className="file-menu"><summary>Menu ▾</summary><div><button onClick={()=>setCreating(true)}>Tạo project</button><button disabled={!runId} onClick={deleteRun}>Xóa lần Extract…</button><button className="danger" onClick={deleteProject}>Xóa project…</button></div></details>}<span className={'save-status '+(saveState==='Đã lưu'?'saved':'')}>● {saveState}</span><button disabled={!project} onClick={()=>save().catch(fail)}><Save size={15}/> Lưu</button></div>
    </header>
    {error&&<div className="error-bar" role="alert">{error}<button onClick={()=>setError('')}><X size={14}/></button></div>}
    {!project?<div className="welcome"><div className="welcome-icon"><Layers size={46}/></div><span className="eyebrow">TỪ TRANG TRUYỆN ĐẾN TỪNG CẢNH</span><h1>Không gian cho câu chuyện của bạn.</h1><p>Tập hợp trang truyện, nhận diện nhân vật và chỉnh sửa từng lời thoại<br/>trong một timeline. Dữ liệu được lưu ngay trên máy.</p><button className="primary" onClick={()=>setCreating(true)}><Plus size={17}/> Tạo project đầu tiên</button><div className="welcome-steps"><span>01 &nbsp; Thêm trang truyện</span><span>02 &nbsp; Trích xuất với Magi v2</span><span>03 &nbsp; Biên tập timeline</span></div></div>:
    <><main className="workspace"><div className="left-resizer"><ResizeHandle axis="x" variable="--left-width" min={230} max={()=>Math.max(230,innerWidth-600)} label="Độ rộng cột cấu hình"/></div><div className="right-resizer"><ResizeHandle axis="x" variable="--right-width" min={270} max={()=>Math.max(270,innerWidth-550)} reverse label="Độ rộng thuộc tính panel"/></div><aside className="left-pane"><div className="pane-heading"><span>TÀI NGUYÊN DỰ ÁN</span><div className="extract-top"><select aria-label="Chế độ trích xuất" value={extractMode} onChange={e=>setExtractMode(e.target.value as 'incremental'|'full')}><option value="incremental">Bổ sung</option><option value="full">Chạy lại toàn bộ</option></select><button aria-label="Bắt đầu trích xuất" title="Bắt đầu trích xuất · sẽ hỏi xác nhận" disabled={!project.pages.length||busy} onClick={()=>start().catch(fail)}><Play size={13}/></button></div></div><nav className="tabs left-tabs">{[['images',<ImageIcon size={17}/>,'Ảnh'],['characters',<Users size={17}/>,'Nhân vật'],['config',<Settings2 size={17}/>,'Cấu hình'],['services',<Music2 size={17}/>,'Dịch/Âm']].map(([id,icon,label])=><button key={String(id)} className={left===id?'active':''} onClick={()=>setLeft(String(id))}>{icon}<span>{label}</span></button>)}</nav>
      <div className="left-content">
        {left==='images'&&<><div className="section-title"><h3>Trang truyện <em>{project.pages.length}</em></h3>{button(showImages?<EyeOff size={15}/>:<Eye size={15}/>,'Ẩn/hiện danh sách',()=>setShowImages(!showImages))}</div><label className="upload-zone"><Upload size={23}/><strong>{busy?'Đang tải ảnh…':'Thêm trang truyện'}</strong><span>Chọn nhiều ảnh JPG, PNG, WEBP</span><input aria-label="Upload trang truyện" type="file" multiple accept="image/*" onChange={e=>upload(e.target.files).catch(fail)}/></label><p className="hint">Kéo trang để đổi thứ tự đọc trước khi trích xuất.</p>{showImages&&<div className="page-list">{project.pages.map((p,i)=><div className="page-row" draggable onDragStart={startDrag('page',p.id)} onDragOver={e=>e.preventDefault()} onDrop={e=>drop(e,'page',p.id)} key={p.id} onClick={()=>setSelectedPage(p.id)}><GripVertical size={14}/><img src={asset(p.image)}/><div><strong>{p.name}</strong><span>Trang {String(i+1).padStart(2,'0')}</span></div><button className="icon-btn" title="Bỏ trang khỏi đầu vào" onClick={e=>{e.stopPropagation();mutateProject(v=>{v.pages=v.pages.filter(x=>x.id!==p.id);});if(selectedPage===p.id)setSelectedPage('');}}><X size={14}/></button></div>)}</div>}{!project.pages.length&&<div className="mini-empty">Chưa có trang truyện.<br/>Ảnh gốc luôn được giữ trong project.</div>}</>}
        {left==='characters'&&<><div className="section-title"><h3>Nhân vật <em>{characters.length}</em></h3><button className="icon-btn" title="Thêm nhân vật" onClick={()=>mutateProject(p=>p.characters.push({id:crypto.randomUUID().replaceAll('-',''),name:'Nhân vật mới',color:'#b89cff',gender:''}))}><Plus size={17}/></button></div><p className="hint">Ảnh tham chiếu giúp Magi nhận diện cùng nhân vật qua các trang.</p>{characters.map(c=><div className="character-card" key={c.id}><div className="character-title"><input aria-label="Màu nhân vật" type="color" value={c.color} onChange={e=>mutateProject(p=>{p.characters.find(x=>x.id===c.id)!.color=e.target.value;})}/><input aria-label="Tên nhân vật" value={c.name} onChange={e=>mutateProject(p=>{p.characters.find(x=>x.id===c.id)!.name=e.target.value;})}/><button className="icon-btn" title="Bỏ nhân vật" onClick={()=>mutateProject(p=>{p.characters=p.characters.filter(x=>x.id!==c.id);})}><X size={14}/></button></div><CharacterReference character={c} asset={asset} onChange={patch=>mutateProject(p=>Object.assign(p.characters.find(x=>x.id===c.id)!,patch))} upload={async files=>{const result=await upload(files,true);return result?.image||'';}} loadURL={async url=>{await save();const result=await api<{image:string}>(base+'/references/url','POST',{url});return result.image;}}/><VoiceControls character={c} asset={asset} disabled={taskBusy} upload={uploadVoice} start={startTask} change={voice=>mutateProject(p=>{p.characters.find(x=>x.id===c.id)!.voice=voice;})}/></div>)}<div className="character-card unknown-character"><h3 style={{color:unknown.color}}>Giọng Unknown</h3><label>Màu Unknown<input aria-label="Màu unknown" type="color" value={unknown.color} onChange={e=>mutateProject(p=>{p.unknown_character={...unknown,color:e.target.value};})}/></label><VoiceControls character={unknown} asset={asset} disabled={taskBusy} upload={uploadVoice} start={startTask} change={voice=>mutateProject(p=>{p.unknown_character={...unknown,voice};})}/><p className="hint">Giọng dùng cho các người nói chưa nhận diện. Chỉ cần clone một lần.</p></div></>}
        {left==='services'&&cfg.translation&&<GlobalServices cfg={cfg} change={setOption} start={startTask} canRun={!!edits}/>}

        {left==='config'&&<><h3>Global prompt</h3><p className="hint">Định hướng chung cho toàn dự án. Chưa gửi đến API tạo video.</p><textarea className="global-prompt" placeholder="Phong cách hình ảnh, chuyển động, nhịp kể…" value={project.global_prompt} onChange={e=>mutateProject(p=>{p.global_prompt=e.target.value;})}/><label>Tên project<input value={project.name} onChange={e=>mutateProject(p=>{p.name=e.target.value;})}/></label><h3>Thiết lập trích xuất</h3><div className="field-pair"><label>Tỉ lệ upscale<select aria-label="Tỉ lệ upscale" value={cfg.upscale?.scale??2} onChange={e=>setOption(['upscale','scale'],Number(e.target.value))}>{[1,1.5,2,3,4].map(n=><option key={n} value={n}>×{n}</option>)}</select></label><label>Tile (pixel)<input aria-label="Tile upscale" type="number" min="32" max="1024" step="32" value={cfg.upscale?.tile??128} onChange={e=>setOption(['upscale','tile'],Number(e.target.value))}/></label></div><p className="hint">Tile là mảnh ảnh xử lý mỗi lượt. Nhỏ hơn dùng ít VRAM hơn nhưng có thể chậm hơn. Tỉ lệ upscale mặc định ×2; đổi tỉ lệ sẽ phải xử lý lại ảnh.</p><label>Hướng đọc<select value={cfg.direction||'jp'} onChange={e=>setOption(['direction'],e.target.value)}><option value="jp">Nhật · Phải → Trái</option><option value="vn">Việt · Trái → Phải</option></select></label><div className="field-pair"><label>Panel tối thiểu (%)<input type="number" min="0.1" max="100" step="0.1" value={(cfg.min_panel_area||0)*100} onChange={e=>setOption(['min_panel_area'],Number(e.target.value)/100)}/></label><label>Lọc panel lồng (%)<input type="number" min="1" max="100" value={(cfg.nested_ratio||0)*100} onChange={e=>setOption(['nested_ratio'],Number(e.target.value)/100)}/></label></div><label className="checkbox"><input type="checkbox" checked={cfg.ocr?.enabled||false} onChange={e=>setOption(['ocr','enabled'],e.target.checked)}/> OCR hàng loạt sau khi trích xuất</label><label>Engine OCR<select value={cfg.ocr?.engine||'tesseract'} onChange={e=>setOption(['ocr','engine'],e.target.value)}>{engines.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label><OCRLanguage engine={cfg.ocr?.engine||'tesseract'} value={cfg.ocr?.[cfg.ocr?.engine]?.language||'vi'} onChange={v=>setOption(['ocr',cfg.ocr.engine,'language'],v)}/><div className="info-note"><Sparkles size={16}/> Real-ESRGAN ×{cfg.upscale?.scale??2} → Magi v2 → OCR<br/>Model chạy lần lượt để tiết kiệm VRAM.</div><details><summary><Braces size={15}/> Toàn bộ YAML</summary><textarea aria-label="Cấu hình YAML" className="code config-editor" spellCheck={false} value={config} onChange={e=>configChange(e.target.value)}/></details></>}
      </div><div className="extract-area">{extractPlan&&<div className="extract-plan" data-testid="extract-plan">Dùng lại <b>{extractPlan.reused_pages}</b> trang · Cần xử lý <b>{extractPlan.processing_pages}</b> trang{Object.values(extractPlan.reasons).includes('settings_changed')&&<small>Cấu hình xử lý/nhân vật đã đổi; các trang không còn khớp sẽ được xử lý lại.</small>}</div>}{status&&['queued','running','cancelling'].includes(status.state)&&<button className="danger full cancel-extract" disabled={status.state==='cancelling'} onClick={()=>api<Status>(base+`/extracts/${runId}/cancel`,'POST').then(setStatus).catch(fail)}>Dừng trích xuất</button>}{status&&<div className="job-status"><span className={status.state==='running'?'pulse':''}/> {stageNames[status.stage]||status.state}<small>{status.page}/{status.total} trang</small></div>}<span>{extractMode==='incremental'?'Giữ chỉnh sửa cũ · Nối panel mới cuối timeline':'Chạy lại model toàn bộ · Tạo timeline mới'}</span></div>
    </aside>
    {selectedPage&&project.pages.some(p=>p.id===selectedPage)?<PageEditor key={selectedPage} page={project.pages.find(p=>p.id===selectedPage)!} base={base} runId={runId} characters={speakers} asset={asset} close={()=>setSelectedPage('')} change={layout=>mutateProject(p=>{p.pages.find(x=>x.id===selectedPage)!.layout=layout;})}/>:<><section className="viewer"><div className="viewer-top"><span>KHUNG XEM TRƯỚC</span><span className="viewer-counter">{selected?`${(edits?.order.indexOf(selected)||0)+1} / ${panels.length} panel`:'Chưa chọn panel'}</span></div><div className="canvas">{panel?<div className="image-stage" style={{transform:`scale(${zoom})`}}><img alt="Panel đang chọn" className="panel-image" src={panelAsset(panel)}/><svg viewBox={`0 0 ${panel.bbox[2]-panel.bbox[0]} ${panel.bbox[3]-panel.bbox[1]}`} preserveAspectRatio="xMidYMid meet">{textBoxes&&panel.texts.map(t=>{const b=t.bbox.panel!;return <rect key={t.id} x={b[0]} y={b[1]} width={b[2]-b[0]} height={b[3]-b[1]} stroke="#a997ff"/>;})}{charBoxes&&panel.characters.map(c=>{const b=c.bbox.panel!;return <g key={c.id}><rect x={b[0]} y={b[1]} width={b[2]-b[0]} height={b[3]-b[1]} stroke={speakerColor(c.character_id)}/><text x={b[0]+4} y={b[1]+18} fill={speakerColor(c.character_id)}>{speakerName(c.character_id)}</text></g>;})}</svg></div>:<div className="viewer-empty"><div><ScanText size={40}/></div><h2>{status?.state==='running'?'Đang đọc câu chuyện…':'Mỗi khung hình, một câu chuyện.'}</h2><p>{project.pages.length?'Bấm trích xuất để tách panel và nhận diện nhân vật.':'Thêm trang truyện ở cột trái để bắt đầu.'}</p><span>Ảnh nâng cấp ×{cfg.upscale?.scale??2} · Bố cục · Nhân vật · Hội thoại</span></div>}</div><div className="viewer-toolbar"><div>{button(<ScanText size={17}/>,'Bật/tắt bbox chữ',()=>setTextBoxes(!textBoxes),textBoxes)}{button(<Users size={17}/>,'Bật/tắt bbox nhân vật',()=>setCharBoxes(!charBoxes),charBoxes)}</div><span>{panel?`${panel.bbox[2]-panel.bbox[0]} × ${panel.bbox[3]-panel.bbox[1]}`:'—'}<span className="toolbar-divider">|</span> {Math.round(zoom*100)}%</span><div>{button(<ZoomOut size={17}/>,'Thu nhỏ',()=>setZoom(Math.max(.25,zoom-.25)))}{button(<ZoomIn size={17}/>,'Phóng to',()=>setZoom(Math.min(3,zoom+.25)))}</div></div></section>
    <PanelInspector panel={panel} edit={panelEdit} cfg={cfg} characters={speakers} right={right} setRight={setRight} change={editPanel}
      start={startTask} onDrag={startDrag} onDrop={drop} asset={asset} engine={ocrEngine} setEngine={setOcrEngine} ocr={reOCR}
      proposal={proposal} applyOCR={applyOCR} clearOCR={()=>setProposal(null)} busy={taskBusy}/></>}
</main>
    <section className="timeline"><ResizeHandle axis="y" variable="--timeline-height" min={180} max={()=>innerHeight-300} reverse label="Chiều cao timeline"/><TaskStatus task={task} onDismiss={()=>setTask(null)} asset={asset} onApply={()=>applyTask()} onCancel={()=>api<Task>(base+`/tasks/${task!.id}/cancel`,'POST').then(setTask).catch(fail)}/><div className="timeline-heading"><div className="timeline-tabs"><button className={!deleted?'active':''} onClick={()=>setDeleted(false)}><Layers size={15}/> Timeline <em>{edits?.order.filter(id=>!edits.panels[id].hidden).length||0}</em></button><button className={deleted?'active':''} onClick={()=>setDeleted(true)}><Trash2 size={14}/> Đã xóa <em>{edits?.order.filter(id=>edits.panels[id].hidden).length||0}</em></button></div><div className="timeline-summary">{totalDuration.toFixed(1)} giây <span>·</span> {edits?.batches.length||0} batch <span>·</span><button className="subtle" disabled={!edits} onClick={()=>mutateEdits(e=>{const colors=['#6956b8','#247e91','#9a6239','#8a4c78','#48865d'];e.batches.push({id:crypto.randomUUID(),color:colors[e.batches.length%colors.length],context:''});})}><Plus size={13}/> Batch</button></div></div>
      <div className="context-bar"><span className="batch-time">{batch?edits!.order.filter(id=>!edits!.panels[id].hidden&&edits!.panels[id].batch_id===batch.id).reduce((n,id)=>n+edits!.panels[id].duration,0).toFixed(2)+'s / batch':'—'}</span><span className="eyebrow">{batch?batch.id.startsWith('batch_')?`BATCH ${Number(batch.id.slice(6))+1}`:'BATCH':'BATCH CONTEXT'}</span><input aria-label="Ngữ cảnh batch" disabled={!batch} value={batch?.context||''} placeholder="Thêm ngữ cảnh cho batch (không bắt buộc)…" onChange={e=>mutateEdits(v=>{v.batches.find(b=>b.id===batch?.id)!.context=e.target.value;})}/>{panelEdit&&<input aria-label="Prompt panel" className="panel-prompt" placeholder="Prompt riêng cho panel…" value={panelEdit.prompt} onChange={e=>editPanel(p=>{p.prompt=e.target.value;})}/>}</div>
      <div className="timeline-track">{edits?(deleted?<div className="deleted-panels">{edits.order.filter(id=>edits.panels[id].hidden).map(id=>{const p=panels.find(p=>p.id===id)!;return <div className="deleted-card" key={id}><img src={panelAsset(p)} onClick={()=>setSelected(id)}/><button onClick={()=>mutateEdits(e=>{e.panels[id].hidden=false;})}><RotateCcw size={13}/> Khôi phục</button></div>;})}{!edits.order.some(id=>edits.panels[id].hidden)&&<div className="timeline-empty">Không có panel đã ẩn.</div>}</div>:edits.batches.map((b,i)=><React.Fragment key={b.id}><div className="batch-group" style={{'--batch-color':b.color} as React.CSSProperties} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(drag.current?.kind==='panel'){const id=drag.current.id;mutateEdits(v=>{v.panels[id].batch_id=b.id;});drag.current=null;}}}><div className="batch-label"><span/>{String(i+1).padStart(2,'0')} <span className="batch-label-text">{b.context||'Chưa có ngữ cảnh'}</span><small>{edits.order.filter(id=>!edits.panels[id].hidden&&edits.panels[id].batch_id===b.id).reduce((n,id)=>n+edits.panels[id].duration,0).toFixed(2)}s · {edits.order.filter(id=>!edits.panels[id].hidden&&edits.panels[id].batch_id===b.id).length} panel</small></div><div className="batch-panels">{edits.order.filter(id=>!edits.panels[id].hidden&&edits.panels[id].batch_id===b.id).map(id=>{const p=panels.find(p=>p.id===id)!,ep=edits.panels[id];return <div data-testid="timeline-panel" data-panel-id={id} className={'timeline-panel '+(selected===id?'selected':'')} key={id} draggable onDragStart={startDrag('panel',id)} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.stopPropagation();drop(e,'panel',id);}} onClick={()=>{setSelectedPage('');setSelected(id);setZoom(1);}}><div className="thumbnail"><img src={panelAsset(p)}/><span className="panel-number">{String(edits.order.indexOf(id)+1).padStart(2,'0')}</span><span className="panel-duration">{ep.duration.toFixed(2)}s</span><button title="Ẩn panel" onClick={e=>{e.stopPropagation();mutateEdits(v=>{v.panels[id].hidden=true;});}}><X size={12}/></button></div><div className="panel-subtitle">{ep.dialogues.length?ep.dialogues.map(d=><span key={d.id} style={{color:speakerColor(d.speaker_id)}}><i style={{background:speakerColor(d.speaker_id)}}/>{d.text||'…'}{d.translation?.text&&<small className="timeline-translation">{d.translation.text}</small>}</span>):<span className="no-dialogue">Cảnh · Không có lời thoại</span>}</div></div>;})}{!edits.order.some(id=>!edits.panels[id].hidden&&edits.panels[id].batch_id===b.id)&&<div className="batch-drop">Kéo panel vào đây</div>}</div></div>{i<edits.batches.length-1&&<div className="batch-boundary" title="Kéo ranh giới hoặc bấm mũi tên để chuyển panel" draggable onDragStart={e=>{e.dataTransfer.setData('text/plain','boundary');drag.current={kind:'boundary',id:String(i)};}} onDragEnd={e=>{const x=e.currentTarget.getBoundingClientRect().x;if(e.clientX&&Math.abs(e.clientX-x)>20)moveBoundary(i,e.clientX>x?1:-1);drag.current=null;}}><button title="Thu batch trái" onClick={()=>moveBoundary(i,-1)}><ChevronLeft size={12}/></button><div/><button title="Mở batch trái" onClick={()=>moveBoundary(i,1)}><ChevronRight size={12}/></button></div>}</React.Fragment>)):<div className="timeline-empty"><Layers size={24}/><span>Timeline của bạn sẽ xuất hiện tại đây</span><small>Trích xuất ảnh để bắt đầu sắp xếp các cảnh</small></div>}</div>
      <div className="audio-track"><Music2 size={15}/><span>Âm thanh</span><span className="todo-badge">TẠO THEO YÊU CẦU</span><div/></div><footer><span><span className="status-dot"/> Tất cả dữ liệu lưu trên máy</span><span>Magi v2 <span>·</span> Real-ESRGAN ×{cfg.upscale?.scale??2} <span>·</span> {cfg.ocr?.enabled?engines.find(([v])=>v===cfg.ocr.engine)?.[1]:'OCR thủ công'}</span></footer>
    </section></>}
    {jobsOpen&&<JobsDialog close={()=>setJobsOpen(false)} open={async j=>{if(latest.current.project?.id!==j.project_id)await selectProject(j.project_id);if(j.run_id)await openRun(j.run_id,j.project_id);}} apply={async j=>{await save();const prefix=`/projects/${j.project_id}`;const project=await api<Project>(prefix);const run=j.run_id?await api<{edits:Edits}>(prefix+`/extracts/${j.run_id}`):null;const result=await api<{project:Project;edits:Edits;task:Task}>(prefix+`/tasks/${j.id}/apply`,'POST',{project_revision:project.revision,revision:run?.edits.revision});if(latest.current.project?.id===j.project_id){latest.current.project=result.project;setProject(result.project);if(j.run_id===latest.current.runId&&result.edits){latest.current.edits=result.edits;setEdits(result.edits);}}}}/>}
    {videoOpen&&project&&<VideoDialog base={base} runId={runId} options={cfg.video} change={value=>setOption(['video'],value)} save={save} asset={asset} close={()=>setVideoOpen(false)}/>}
    {creating&&<div className="modal-backdrop"><form className="modal" onSubmit={e=>{e.preventDefault();createProject().catch(fail);}}><div className="section-title"><h2>Tạo project</h2><button type="button" className="icon-btn" onClick={()=>setCreating(false)}><X size={18}/></button></div><p>Một không gian riêng cho ảnh, nhân vật và các lần trích xuất.</p><label>Tên project<input autoFocus value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Tên câu chuyện của bạn"/></label><button className="primary full" type="submit"><Plus size={16}/> Tạo project</button></form></div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
