import type {Character, Dialogue, Edits, TimingSettings} from './types';
import {translationOf} from './translations';
export const defaultTiming:TimingSettings={mode:'manual',min_seconds:1,words_per_minute:180,text_source:'original',dialogue_gap:.2};
export const textOf=(d:Dialogue,source:string,language?:string)=>source==='translation'?translationOf(d,language)?.text||'':d.text;
export function audioCurrent(d:Dialogue,characters?:Character[]){return !!d.audio&&d.audio.input_text===textOf(d,d.audio.text_source,d.audio.translation_language)&&d.audio.speaker_id===d.speaker_id&&(!characters||(characters.find(c=>c.id===d.speaker_id)||characters.find(c=>c.id==='unknown'))?.voice?.prompt===d.audio.voice_id);}
export function recalculate(edits:Edits,global:Partial<TimingSettings>,characters?:Character[]){
  for(const panel of Object.values(edits.panels)){
    const settings={...defaultTiming,...global,...panel.timing};
    if(settings.mode==='manual'){panel.duration_source='manual';continue;}
    const lines=panel.dialogues.filter(d=>textOf(d,settings.text_source,settings.translation_language).trim());
    if(settings.mode==='text'){
      const words=lines.reduce((n,d)=>n+(textOf(d,settings.text_source,settings.translation_language).match(/[\u3040-\u30ff\u3400-\u9fff]|[\p{L}\p{N}]+/gu)||[]).length,0);
      panel.duration=Math.round((settings.min_seconds+words*60/Math.max(1,settings.words_per_minute))*1000)/1000;
      panel.duration_source='text';
    }else if(lines.every(d=>audioCurrent(d,characters))){
      panel.duration=Math.round((settings.min_seconds+lines.reduce((n,d)=>n+(d.audio_edit?.muted?0:Math.max(0,Math.min(d.audio!.duration,d.audio_edit?.end??d.audio!.duration)-(d.audio_edit?.start||0))),0)+Math.max(0,lines.length-1)*settings.dialogue_gap)*1000)/1000;
      panel.duration_source='audio';
    }else{panel.duration=Math.max(settings.min_seconds,panel.duration);panel.duration_source='audio_pending';}
  }
  return edits;
}
