# HANDOFF — freechecklists.net archive → OCR → OCL JSON pipeline

Written 2026-08-12. Pick up here in a fresh session. The task in one line:
**OCR the 257 archived PDFs using Baidu Unlimited-OCR (on KITDEV003), convert the
Word/spreadsheet files to text, then convert everything to the project's OCL JSON
format to populate our replacement checklists.**

---

## 1. Project context & the IP boundary (critical)

- The project (`openchecklists/openchecklists`) is building a **full replacement
  for freechecklists.net** with new features. The site author gave permission to
  reuse **all functionality and all content**, but **not their software** — we
  write our own implementation.
- **NOT limited to public-domain sources** — `sources/public-domain.json` is one
  manifest, not the whole project. Everything in the archive is reusable.
- Saved to memory: `freechecklists-replacement` (project memory file).

## 2. The archive (COMPLETE — all content already downloaded)

Location: **`/home/node/workspace/openchecklists/freechecklists-archive/`**
(outside the git repo deliberately — see §7 gotchas).

```
freechecklists-archive/
  checklists/<Manufacturer>/<Model>/<file>   606 files: 257 PDF (1.1 GB), 179 .doc,
                                             71 .xls, 67 .zip, 9 .htm, 8 .jpg, 4 .docx,
                                             3 .wps, 2 .xlsx, 2 .xlr, 1 each .ods/.rtf/.odg
  sim-checklists/                            133 simulator zips
  model-pages/                               290 archived model page HTML
  site-assets/                               92 manufacturer logos + 9 images
  site-assets/pages/                         6 remaining HTML pages (index, caravan, newest, simchecklists, webban, submit)
  index.json / index.csv                     685 resources, fully searchable
  aircraft-catalog.json / .csv               295 aircraft / 98 manufacturers (factual reference)
  data/model_pages.txt                       all 295 /Resources/ URLs
  data/sim_checklists.json                   134 zip URLs
  data/download_results.json                 per-file outcome (17 documented broken source links)
  data/download.log                          full download log
  tools/download.py, build_index.py, run_download.sh   (download already DONE — scripts kept for reference/resume)
```

The archive README.md states the permission boundary. Keep contributor attributions.

## 3. OCR pipeline — where it stands

### What's set up (already on KITDEV003)
- **Unlimited-OCR** = Baidu's `baidu/Unlimited-OCR` (3B MoE vision model, MIT).
- Model weights cached at `C:\Users\kitadmin\.cache\huggingface\hub\models--baidu--Unlimited-OCR` (6.3 GB, snapshot `07dea832…`).
- Runtime venv: `C:\AI-Models\unlimited-ocr\venv\` (torch 2.6.0+cu124, transformers 4.57.1 **pinned** — v5 breaks the custom code).
- FastAPI server: `C:\AI-Models\unlimited-ocr\server.py`, port **8765**, model loads ~20s, ~6.2 GB VRAM.
- Manage script: `C:\AI-Models\unlimited-ocr\manage-ocr-server.ps1` (start/stop/status/logs).
- Client CLI on this container: **`/home/node/workspace/kit-lab/tools/ocr-cli.py`** (auto-starts server via SSH, `pdf`/`image`/`status`/`start`/`stop`).
- Hardware: NVIDIA RTX 3070 8 GB, disk 2.6 TB free.

### Verified working ✅
Ran `infer_multi()` directly on KITDEV003 (venv python) — clean OCR output on a test image. The model is fine.

### Known server bugs (fix before batch use)
1. **`/ocr/pdf` passed `base_size`/`crop_mode` to `infer_multi()`** — invalid kwargs → 500. **PATCHED** in server.py already (removed those two kwargs from the `infer_multi` call). Confirm on disk: the `infer_multi` call should have only `image_size=1024, max_length=32768, no_repeat_ngram_size=35, ngram_window=1024, save_results=True`.
2. **Both handlers block the FastAPI event loop** — `async def ocr_image`/`ocr_pdf` run the blocking model call inline, so real requests stall (>55 s, looked like a hang). **Fix: change them to plain `def` (sync)** — uvicorn runs sync endpoints in a thread pool. Or wrap inference in `run_in_executor`.
3. `/ocr/image` once returned `[Errno 22] Invalid argument` — re-investigate after the sync fix; likely tied to the async/blocking issue or the temp-file path.

### The BLOCKER (current)
**The container's Tailscale mesh is down** — `tailscaled` process and binary are gone from this container. KITDEV003 (`100.64.0.8`) is unreachable:
- `ssh kitdev003` → `Connection timed out` (host = 100.64.0.8 per `~/.ssh/config`).
- The mesh DNS resolves `kitdev003.mesh.keylinkit.net → 100.64.0.8`, but that IP won't connect.
- **KITVM3 is still reachable** via `ssh kitvm3` (Cloudflare tunnel, host `kitvm3.keylinkit.net`) and `ssh kitvm3-jump` (keylinkit.vpnplus.to:223). From KITVM3, LAN scan found 192.168.0.209/.210/.211(MedRecs VM)/.219 up, but the KITDEV003 **host** IP is unconfirmed and slow to probe.
- No `tailscale`/`tailscaled` binary on the container → can't restore the mesh from inside.

**To unblock:** (a) restart the container/harness to restore tailscale; or (b) get KITDEV003's LAN IP and SSH-tunnel port 8765 through KITVM3; or (c) run the OCR batch *directly on KITDEV003* via a script (see below) when any route exists.

### Recommended runner once reachable (bypasses the buggy server)
The model works directly. Write a batch script that runs **on KITDEV003** with the venv python:
1. Iterate the 257 PDFs (uploaded to `C:\AI-Models\unlimited-ocr\input\`).
2. For each PDF: render pages with `fitz` (pymupdf, in venv) at ~150-200 DPI, call `MODEL.infer_multi(tokenizer, prompt="<image>Multi page parsing.", image_files=pages, output_path=..., image_size=1024, max_length=32768, no_repeat_ngram_size=35, ngram_window=1024, save_results=True)`.
3. Save each result to `output/<model>/<file>.md`. Resumable, logged.
The `ocr-diag.py` at `/home/node/workspace/kit-lab/tools/ocr-diag.py` is a working reference for the exact call.

### Batch plan (257 PDFs)
- Transfer 1.1 GB of PDFs container → KITDEV003 (SCP once connected).
- RTX 3070: expect minutes-to-tens-of-minutes per large manual; the full set is **many hours** — run in background with a watchdog (pattern already used for the download).
- Output Markdown (reading order, tables intact) → pull back to the container.

## 4. Conversion pipeline (can be built locally NOW — no KITDEV003 needed)

### Word/spreadsheet → text (task 7)
Process the non-PDF files in `checklists/**`:
- `.doc/.docx/.wps/.rtf` → text (LibreOffice headless or `textract`/`antiword`; docx via `python-docx`).
- `.xls/.xlsx/.ods/.xlr` → extract cell data (openpyxl/xlrd/odfpy).
- `.htm` → strip HTML to text. `.jpg` → feed to the same OCR (they're images).
- `.zip` (67) → extract first; contents may include PDFs/docs to process too.
Output: a `text/` mirror tree, one `.txt`/`.md` per source file, with the same `<Mfr>/<Model>/` layout.

### Text → OCL JSON (task 8) — LLM-assisted, dual-pass
- Target format: **`open-checklist-1.0.schema.json`** (`schema/` in the repo) + `examples/*.ocl.json`. Structure: `sections[] → items[] {type:"action", text, response, tickable}`; top-level `aircraft`, `units`, `provenance`, `verification`, `rights`.
- The roadmap `docs/04-roadmap.md` §2 designs this: Stage 3 structured transcription (model emits schema-conformant JSON directly), Stage 4 **dual independent pass + diff** (numbers and item counts must agree), Stage 5 schema/plausibility validation (`tools/validate.py`), Stage 6 human review. Nothing merges automatically.
- Feed OCR'd Markdown / converted text to an LLM → OCL JSON; run twice with different framing and diff.

## 5. Key references
- `docs/04-roadmap.md` — full OCR pipeline + site design (Stages 0-6).
- `schema/open-checklist-1.0.schema.json` — OCL JSON schema.
- `tools/validate.py` — validator (`--strict --check-form`).
- `sources/public-domain.json` — the one PD-only manifest (NOT the whole project).
- `examples/*.ocl.json` — example OCL files (172SP normal, etc.).
- `tools/ocr-cli.py`, `tools/ocr-diag.py` (kit-lab) — OCR client + diagnostic.
- Vault items: `KIT-Dev Server` (KIT-Dev Linux SSH), `KITDEV003` (host login), `KIT VMs local kitadmin (break-glass)`, `Admin Computer Credentials`. `bw` is pre-authed in this container.
- SSH config `~/.ssh/config`: `kitdev003` → 100.64.0.8 (mesh, DOWN), `kitvm3` → cloudflared (UP), `kitvm3-jump` → vpnplus (UP), `kit-dev` → proxyjump (needs mesh/banner).

## 6. Immediate next steps (in order)
1. **Restore KITDEV003 reachability** (restart container/tailscale, or get its LAN IP + tunnel via KITVM3).
2. Apply the **sync-endpoint fix** to `server.py` (change `async def ocr_image`/`ocr_pdf` → `def`), restart via `ocr-cli.py stop/start`, re-run the smoke test (`ocr-cli.py pdf` on a small PDF) — expect OCR text back in seconds.
3. Upload the 257 PDFs to KITDEV003 and run the batch runner (background + watchdog) → Markdown.
4. Build the Word/spreadsheet → text converter (local).
5. LLM-assisted text → OCL JSON (dual-pass) + `tools/validate.py`.

## 7. Gotchas / hard-won lessons
- **Concurrent session**: another Claude session (`--resume 8aa6848e`) works in the `openchecklists` repo and its git operations wiped an in-repo untracked dir once. Keep the archive **outside the repo** (`freechecklists-archive/`).
- **The site's hotlink protection** was session-scoped (fpath zones rotate per session) — that's why the download used per-file fresh fetches. Docs in `freechecklists-archive/tools/download.py`.
- **One file/minute rate limit** was the user's explicit requirement for the site download (DONE). Don't hammer the site further; it's shutting down.
- **transformers is pinned to 4.57.1** on the OCR venv — v5 breaks Unlimited-OCR's custom code. Don't upgrade it.
- **Headscale mesh (100.64.0.0/16)** is the normal container↔VM path; it can drop without warning (current state). Cloudflare tunnel to KITVM3 is the fallback route.
- The `lab-kitvm3`/`lab-kitdev003` MCP servers route through these same SSH paths — if the mesh is down, `kitvm3_run_powershell` may still work (it reaches KITVM3), but `kitdev003_run_powershell` will not.

## 8. Open questions for the user
- Confirm the OCR batch can consume the GPU for hours (it's on a shared Windows host).
- Target aircraft priority for the FIRST OCL files (roadmap says: types with zero coverage anywhere, e.g. Part 103/experimental, over the tenth Cessna 172 variant).
- Whether to run the OCL conversion against ALL 606 files or a curated subset per aircraft.
