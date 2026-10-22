import {useEffect,useState} from 'react';
import {api} from './api';
import type {Language} from './types';
let cached:Promise<Language[]>|undefined;
export function useCatalog(){
  const [items,setItems]=useState<Language[]>([]);
  useEffect(()=>{cached ||= api<Language[]>('/languages');cached.then(setItems).catch(()=>{cached=undefined;});},[]);
  return items;
}
export function LanguageSelect({value,onChange,label,options,auto=false}:{value:string;onChange:(v:string)=>void;label:string;options?:Language[];auto?:boolean}){
  const catalog=useCatalog(),items=options?.length?options:catalog;
  const code=value.toLowerCase().split('+')[0],entry=catalog.find(l=>l.code===code||l.aliases?.includes(code)||Object.values(l.ocr_codes||{}).includes(code));
  return <label>{label}<div className="language-select">{entry?.flag&&<img alt="" src={`/flags/${entry.flag}.svg`}/>}<select aria-label={label} value={value} onChange={e=>onChange(e.target.value)}>{auto&&<option value="auto">Tự nhận diện</option>}{value!=='auto'&&!items.some(l=>l.code===value)&&<option value={value}>{value}</option>}{items.map(l=>{const known=catalog.find(c=>c.code===l.code||c.aliases?.includes(l.code)||Object.values(c.ocr_codes||{}).includes(l.code));return <option key={l.code} value={l.code}>{l.code==='jpn_vert'?l.name:known?.name||l.name} ({l.code})</option>;})}</select></div></label>;
}
