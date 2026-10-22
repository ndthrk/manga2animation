import type {Dialogue,Translation} from './types';
// Đọc cả định dạng cũ, nhưng mỗi ngôn ngữ chỉ có một bản dịch hiện hành.
export function translationOf(line:Dialogue,language?:string):Translation|undefined{
  return language?(line.translations?.[language]||(line.translation?.target===language?line.translation:undefined)):line.translation||Object.values(line.translations||{})[0];
}
export function setTranslation(line:Dialogue,value:Translation){
  line.translations ||= {};
  if(line.translation)line.translations[line.translation.target] ||= line.translation;
  line.translations[value.target]=value;line.translation=value;
}
