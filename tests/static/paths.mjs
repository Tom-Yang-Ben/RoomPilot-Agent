// 正式前端在磁碟上的位置——Node 測試這一側的單一來源。
// Python 那側是 backend/paths.py；目錄搬家時兩個檔案要一起改，其餘檔案都不用動。
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const STATIC_DIR = path.resolve(HERE, "..", "..", "frontend");
