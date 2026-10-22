export async function api<T>(url:string, method='GET', data?:unknown):Promise<T> {
  const response=await fetch('/api'+url, {method, headers:data instanceof FormData?{}:{'Content-Type':'application/json'}, body:data===undefined?undefined:data instanceof FormData?data:JSON.stringify(data)});
  if(!response.ok) {let error;try{error=await response.json();}catch{throw new Error(response.statusText);}throw new Error(error.detail||response.statusText);}
  return response.json();
}
