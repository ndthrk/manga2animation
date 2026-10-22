// Giữ thay đổi đang gõ trong lúc HTTP lưu/áp dụng kết quả chưa trả về.
export function mergeServer<T>(before:T,current:T,remote:T):T{
  if(JSON.stringify(before)===JSON.stringify(current))return structuredClone(remote);
  if(Array.isArray(current)&&Array.isArray(before)&&Array.isArray(remote)){
    return current.map(item=>{
      if(item&&typeof item==='object'&&'id' in item){
        const old=before.find(x=>x?.id===item.id),next=remote.find(x=>x?.id===item.id);
        return old&&next?mergeServer(old,item,next):item;
      }
      return item;
    }) as T;
  }
  if(current&&remote&&before&&typeof current==='object'&&typeof remote==='object'&&typeof before==='object'){
    const result={...current} as Record<string,unknown>;
    for(const key of Object.keys(remote)){
      const a=(before as Record<string,unknown>)[key],b=(current as Record<string,unknown>)[key],c=(remote as Record<string,unknown>)[key];
      result[key]=key==='revision'||key==='saved_at'?c:mergeServer(a,b,c);
    }
    return result as T;
  }
  return current;
}
