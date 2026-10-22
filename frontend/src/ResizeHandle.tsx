import type {PointerEvent} from 'react';
// Lưu kích thước vào trình duyệt; kéo và phím mũi tên đều dùng cùng giới hạn.
export function ResizeHandle({axis,variable,min,max,reverse=false,label}:{axis:'x'|'y';variable:string;min:number;max:()=>number;reverse?:boolean;label:string}){
  const value=()=>parseFloat(getComputedStyle(document.documentElement).getPropertyValue(variable))||min;
  const write=(next:number)=>{next=Math.max(min,Math.min(max(),next));document.documentElement.style.setProperty(variable,`${next}px`);localStorage.setItem(variable,String(next));};
  function begin(e:PointerEvent){e.preventDefault();const start=axis==='x'?e.clientX:e.clientY,previous=value();e.currentTarget.setPointerCapture(e.pointerId);const node=e.currentTarget as HTMLElement;node.onpointermove=event=>write(previous+((axis==='x'?event.clientX:event.clientY)-start)*(reverse?-1:1));node.onpointerup=node.onpointercancel=()=>{node.onpointermove=null;};}
  return <div role="separator" aria-label={label} aria-orientation={axis==='x'?'vertical':'horizontal'} tabIndex={0} className={`resize-handle resize-${axis} ${reverse?'reverse':''}`} onPointerDown={begin} onKeyDown={e=>{const d=['ArrowLeft','ArrowUp'].includes(e.key)?-1:['ArrowRight','ArrowDown'].includes(e.key)?1:0;if(d){e.preventDefault();write(value()+d*20*(reverse?-1:1));}}}/>;
}
for(const key of ['--left-width','--right-width','--timeline-height']){const value=Number(localStorage.getItem(key));if(value>0)document.documentElement.style.setProperty(key,`${value}px`);}
