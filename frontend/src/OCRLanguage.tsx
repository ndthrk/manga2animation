import {LanguageSelect} from './LanguageSelect';
import {useLanguages} from './ServiceSettings';
export function OCRLanguage({engine,value,onChange}:{engine:string;value:string;onChange:(v:string)=>void}){
  const languages=useLanguages().ocr_languages;
  if(engine==='paddleocr'||engine==='tesseract')return <><LanguageSelect label={engine==='tesseract'?'Ngôn ngữ Tesseract':'Ngôn ngữ PaddleOCR'} value={value} options={languages[engine]||[]} onChange={onChange}/><p className="hint">{engine==='tesseract'?'Cần cài đúng traineddata. Chọn Nhật chữ dọc nếu đọc chữ dọc; nhiều ngôn ngữ có thể ghép bằng dấu + trong YAML.':'Ngôn ngữ chọn được chuyển sang mã PaddleOCR tương ứng.'}</p></>;
  return <label>Ngôn ngữ OCR<select disabled value="checkpoint"><option value="checkpoint">{engine==='indra'?'Theo vocabulary của checkpoint ONNX':'Theo checkpoint Magi đang nạp'}</option></select><small>Engine không nhận tham số chọn ngôn ngữ. Đổi checkpoint hoặc dùng Tesseract/PaddleOCR để chọn ngôn ngữ.</small></label>;
}
