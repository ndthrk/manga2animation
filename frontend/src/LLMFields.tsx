import {useId,useState} from 'react';
import {api} from './api';
import type {LLMSettings} from './types';

type Props={provider:string;value:LLMSettings;onChange:(value:LLMSettings)=>void;pull?:(settings:LLMSettings)=>void};
const suggestions:Record<string,string[]>={ollama:['qwen3:1.7b','qwen3:4b','qwen2.5:3b'],openai_compatible:['gpt-4.1-mini','gpt-4o-mini','deepseek-chat']};

export function LLMFields({provider,value,onChange,pull}:Props){
  const ident=useId(),[models,setModels]=useState<{id:string;size?:number}[]>([]),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const set=(key:string,next:unknown)=>onChange({...value,[key]:next});
  async function refresh(){setBusy(true);setMessage('');try{const list=await api<{id:string;size?:number}[]>('/llm/models','POST',{provider,settings:value});setModels(list);setMessage(list.length?`Có ${list.length} model ${provider==='ollama'?'đã tải':'từ API'}.`:'Chưa có model; bạn vẫn có thể nhập tên bên dưới.');}catch(e){setMessage(String(e));}finally{setBusy(false);}}
  const names=Array.from(new Set([...(suggestions[provider]||[]),...models.map(m=>m.id)]));
  return <div className="llm-fields"><label>Base URL<input aria-label="Base URL dịch LLM" value={value.base_url} onChange={e=>set('base_url',e.target.value)} placeholder={provider==='ollama'?'http://127.0.0.1:11434':'https://api.openai.com/v1'}/></label>
    <label>Model dịch<input aria-label="Model dịch LLM" list={ident} value={value.model} onChange={e=>set('model',e.target.value)} placeholder="Chọn gợi ý hoặc nhập tên model riêng"/><datalist id={ident}>{names.map(model=><option key={model} value={model}/>)}</datalist></label>
    <div className="field-pair"><button disabled={busy} onClick={refresh}>{busy?'Đang kết nối…':provider==='ollama'?'Model đã tải':'Lấy model từ API'}</button>{provider==='ollama'&&pull&&<button disabled={!value.model.trim()} onClick={()=>pull(value)}>Tải model đã chọn</button>}</div>
    <div className="llm-model-suggestions">{(suggestions[provider]||[]).map(model=><button key={model} className="subtle" onClick={()=>set('model',model)}>{model}</button>)}</div>
    {message&&<p className="hint" role="status">{message}</p>}
    {provider==='ollama'?<p className="hint">Cần cài và chạy Ollama trước. Model chưa có phải tải weight; qwen3:1.7b khoảng 1,4 GB. Tác vụ dịch trả model khỏi GPU khi xong.</p>:<><label>Biến môi trường API key<input aria-label="Biến API key dịch" value={value.api_key_env||''} onChange={e=>set('api_key_env',e.target.value)} placeholder="LLM_API_KEY"/></label><label>Hoặc API key riêng<input aria-label="API key dịch LLM" type="password" autoComplete="off" value={value.api_key||''} onChange={e=>set('api_key',e.target.value)} placeholder="Bỏ trống để dùng biến môi trường"/></label><p className="hint">Dùng endpoint Chat Completions của dịch vụ hỗ trợ OpenAI-compatible. Tên model tùy tài khoản/server; các tên trên là gợi ý.</p></>}
    <label>Hướng dẫn dịch thêm<textarea aria-label="Hướng dẫn dịch LLM" value={value.system_prompt||''} onChange={e=>set('system_prompt',e.target.value)} placeholder="Cách xưng hô, giữ tên nhân vật, văn phong…"/></label>
    <details><summary>Tham số LLM</summary><div className="field-pair"><label>Temperature<input type="number" min="0" max="2" step=".1" value={value.temperature??.2} onChange={e=>set('temperature',Number(e.target.value))}/></label><label>Token đầu ra tối đa<input aria-label="Token dịch LLM" type="number" min="1" max="32768" value={value.max_tokens} onChange={e=>set('max_tokens',Number(e.target.value))}/></label></div><label>Timeout (giây)<input type="number" min="1" max="1800" value={value.timeout_seconds} onChange={e=>set('timeout_seconds',Number(e.target.value))}/></label>
      {provider==='ollama'?<label>Context length<input type="number" min="512" value={value.context_length||4096} onChange={e=>set('context_length',Number(e.target.value))}/></label>:<><label>Tham số giới hạn token<select value={value.token_parameter||'max_tokens'} onChange={e=>set('token_parameter',e.target.value)}><option value="max_tokens">max_tokens</option><option value="max_completion_tokens">max_completion_tokens</option></select></label><label className="checkbox"><input type="checkbox" checked={value.send_temperature!==false} onChange={e=>set('send_temperature',e.target.checked)}/> Gửi temperature</label><label className="checkbox"><input type="checkbox" checked={!!value.json_mode} onChange={e=>set('json_mode',e.target.checked)}/> JSON mode (khi API hỗ trợ)</label></>}
    </details>
  </div>;
}
