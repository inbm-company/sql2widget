// 브라우저에서 고른 문서를 업로드 가능한 형태로 읽는다. 서버 제한(backend/app/graph_ingestion.py)과 같은 값을 쓴다.
export const MAX_UPLOAD_FILES = 1000;
export const MAX_FILE_BYTES = 2 * 1024 * 1024;
export const MAX_TOTAL_BYTES = 20 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".md", ".txt"];

/** 폴더 선택이면 폴더 기준 상대 경로, 파일 선택이면 파일명을 돌려준다. */
export function uploadPath(file) {
  return file.webkitRelativePath || file.name;
}

/** 지원 확장자이면서 숨김 폴더·파일(.git, .obsidian 등)이 아닌 경로만 올린다. */
export function isUploadable(path) {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  const name = parts[parts.length - 1] || "";
  const lower = name.toLowerCase();
  return !parts.some((part) => part.startsWith("."))
    && SUPPORTED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

/**
 * 선택한 파일을 UTF-8 텍스트로 읽는다.
 * @returns {Promise<{files: {path: string, text: string}[], excluded: number}>}
 */
export async function readUploadFiles(fileList) {
  const selected = Array.from(fileList || []);
  const targets = selected.filter((file) => isUploadable(uploadPath(file)));
  if (targets.length > MAX_UPLOAD_FILES) {
    throw new Error(`한 번에 최대 ${MAX_UPLOAD_FILES.toLocaleString()}개 문서를 올릴 수 있습니다. 하위 폴더를 나눠 올리세요.`);
  }
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const files = [];
  let total = 0;
  for (const file of targets) {
    const path = uploadPath(file);
    if (file.size > MAX_FILE_BYTES) throw new Error(`문서당 최대 2 MiB를 지원합니다: ${path}`);
    total += file.size;
    if (total > MAX_TOTAL_BYTES) throw new Error("한 번에 최대 20 MiB를 올릴 수 있습니다. 하위 폴더를 나눠 올리세요.");
    try {
      files.push({ path, text: decoder.decode(await file.arrayBuffer()) });
    } catch {
      throw new Error(`UTF-8 텍스트 파일이 아닙니다: ${path}`);
    }
  }
  return { files, excluded: selected.length - targets.length };
}
