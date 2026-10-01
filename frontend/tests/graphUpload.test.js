import assert from "node:assert/strict";
import test from "node:test";
import { isUploadable, readUploadFiles, MAX_FILE_BYTES } from "../src/graphUpload.js";

const file = (name, content, relative = "") => {
  const bytes = typeof content === "string" ? new TextEncoder().encode(content) : content;
  return { name, webkitRelativePath: relative, size: bytes.length, arrayBuffer: async () => bytes.buffer };
};

test("only markdown and text outside hidden folders are uploadable", () => {
  assert.equal(isUploadable("vault/a.md"), true);
  assert.equal(isUploadable("vault/B.TXT"), true);
  assert.equal(isUploadable("vault/.obsidian/a.md"), false);
  assert.equal(isUploadable("vault/.hidden.md"), false);
  assert.equal(isUploadable("vault/image.png"), false);
  assert.equal(isUploadable("vault\\win.md"), true);
});

test("folder uploads keep relative paths and count excluded files", async () => {
  const result = await readUploadFiles([
    file("a.md", "# 문서", "vault/notes/a.md"),
    file("b.txt", "본문"),
    file("c.png", "x", "vault/c.png"),
    file("d.md", "x", "vault/.git/d.md"),
  ]);
  assert.deepEqual(result.files, [
    { path: "vault/notes/a.md", text: "# 문서" },
    { path: "b.txt", text: "본문" },
  ]);
  assert.equal(result.excluded, 2);
});

test("a BOM is stripped and invalid UTF-8 or oversized files are rejected", async () => {
  const bom = new Uint8Array([0xef, 0xbb, 0xbf, 0x41]);
  assert.deepEqual((await readUploadFiles([file("a.md", bom)])).files, [{ path: "a.md", text: "A" }]);
  await assert.rejects(readUploadFiles([file("bad.md", new Uint8Array([0xff, 0xfe, 0x41]))]), /UTF-8/);
  await assert.rejects(readUploadFiles([{ ...file("big.md", "x"), size: MAX_FILE_BYTES + 1 }]), /2 MiB/);
});
