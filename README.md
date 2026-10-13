# Digisona

Create a local talking-video persona from your own face and voice recordings. Record or import samples, choose a portrait, preview cloned English speech, and turn it into a downloadable video.

Digisona uses Chatterbox for voice, SadTalker for face animation, and FFmpeg for media processing. No paid API or subscription is required. Internet access is needed for installation and model downloads. Once setup completes, the downloaded assets are reused locally.

## Supported computers

- Windows 10/11 **x64**. macOS, Linux and Windows ARM are not supported by this installer.
- At least **16 GB RAM** recommended. Voice inference runs on CPU.
- An NVIDIA GPU with **4 GB VRAM** is a tested starting point. CPU-only rendering is supported but much slower.
- Allow **25 GB of free disk space** for environments, weights, caches and temporary downloads, plus space for recordings.
- Chrome or Edge for camera and microphone recording.
- Internet access to GitHub, PyPI, PyTorch and Hugging Face during setup.

The working GPU configuration was tested on GTX 1050 4 GB with NVIDIA driver 531.14. Other hardware still needs a short generation test. Modern and unusual GPU architectures may need CPU mode because the face engine uses an older PyTorch build.

## Install

1. Download the repository ZIP using **Code → Download ZIP**, or clone it:

   ```powershell
   git clone https://github.com/Aviseka00/digisona.git
   cd digisona
   ```

2. Extract the ZIP fully into a writable folder. Do not run from inside the ZIP, a protected system folder, or a synchronized network drive.
3. Double-click **install.cmd**. It downloads a checksum-verified uv bootstrap, installs private Python 3.11 and 3.8 runtimes, creates separate environments, fetches the pinned face-engine source, downloads model weights and FFmpeg, and verifies both engines. You do not need to install Python or Git separately when using the ZIP.
4. Keep the installer window open. Setup can take a while and downloads several GB. If a connection fails, rerun install.cmd: completed environments and assets are reused.
5. After installation finishes, double-click **start.cmd**. Keep its server window open and use http://127.0.0.1:8765/.

To force CPU rendering, open a terminal in the extracted folder and run:

```powershell
.\install.cmd -CpuOnly
```

The batch launcher uses PowerShell's `-ExecutionPolicy Bypass` for that installer process only; it does not change your permanent execution policy. Organizations may still block script execution or model downloads. The package does not bypass those restrictions.

If importing PyTorch reports a missing DLL, install Microsoft's supported Visual C++ 2015–2022 x64 Redistributable from https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist and rerun setup. NVIDIA GPU mode requires a suitable installed driver; Digisona does not install or change your driver.

## Create your persona

1. Create a persona in **Capture**.
2. Upload a JPEG, PNG or WebP photo, or record/import a face video in even lighting. Photos can be used directly without recording any face video. For videos, pause on a clear frame with your mouth visible, then choose **Use paused frame as portrait**. A close, sharp head-and-shoulders photo gives better facial detail than a distant full-body image.
3. Record English speech in your normal voice. Add happy, calm and serious samples if desired. Use the microphone meter and sample-quality checks. These checks assess level, clipping and quiet sections; they do not measure identity similarity or background noise.
4. Open **Create**, type your script, and choose a voice sample. Set speed and expression. Optional pronunciation substitutions use `word = spoken spelling`, one per line.
5. Choose **Preview my voice**. Listen first, then approve the video render. Video generation reuses your approved speech.
6. Choose focused portrait or original framing. Original framing preserves the source background and dimensions; choose Draft (256 pixels) or Detail (512 pixels). Detail requires more memory and time. A 720p output is not a native HD face reconstruction.
7. Download MP4 or voice WAV. Search, filter, retry, cancel and delete jobs in the local library.

Photos are limited to 20 MB and 30 megapixels. Audio/video uploads are limited to 100 MB and 90 seconds. Imported face videos use the first 20 seconds; voice references use the first 30 seconds. Scripts support up to 1200 characters. Start with a short sentence before generating longer clips.

## Local storage and configuration

Your recordings and outputs are stored in `data/`. Weights and model caches are in `models/`, tools in `tools/`, and environments in `.venv/` and `.venv-sad/`. Python bootstrap files live in `.runtime/`. These directories and local `config.json` are excluded from Git.

`config.example.json` contains portable defaults. Installation copies it to `config.json` if needed. Empty paths resolve relative to the app folder. `render_device` accepts `auto` or `cpu`; `voice_device` defaults to `cpu`. Absolute paths are optional advanced overrides. Install again after moving the app: Python virtual environments are not guaranteed to survive folder relocation. Existing personal data can be copied separately after reinstalling.

The server binds only to 127.0.0.1 and checks Host/Origin headers. There is no remote hosting, analytics, or cloud media upload. Do not port-forward this local server. Other software running as your user can still read local files. Draft text is also saved in this browser's local storage.

Profile deletion removes its recordings and related jobs after active jobs stop. Standalone setup diagnostics are separate. Deletion requires UI confirmation. Back up your recordings before deleting them or reinstalling in a different folder.

## Troubleshooting

| Problem | Action |
|---|---|
| Setup incomplete | Rerun install.cmd and read the first reported error. |
| GPU memory error | The app retries on CPU. For repeated issues, reinstall with `-CpuOnly`. |
| Unsupported GPU / CUDA failure | Select CPU mode; the older CUDA package does not support every newer GPU. |
| No clear face detected | Select a sharp portrait with your mouth visible and your face facing the camera. |
| Voice differs from your recording | Use clear, natural English speech without music; compare different reference tones. Exact replication is not guaranteed. |
| Port 8765 already in use | Open the existing app or stop its server window. A second launch does not modify its jobs. |
| Server restarted during a job | Retry the interrupted job. Completed speech is reused. |
| Camera/microphone denied | Allow permission for localhost in Chrome or Edge, then try again. |

## Validation

The existing installation passed browser tests for recording, imports, portrait selection, diagnostics, draft persistence, permission-denial recovery and mobile layout. API checks covered malformed media, paths, cancellation, retry and deletion. A real voice-preview-to-full-frame-video test passed and verified speech reuse. Automatic GPU-memory fallback has not been deliberately forced. Fresh installations run model-loading and dependency checks; users should still generate a short video on their own hardware.

## Licenses and model sources

Digisona app code is MIT licensed. Model packages, downloaded assets and tools retain their own licenses; the app license does not override them. See THIRD_PARTY.md.

- Chatterbox: https://github.com/resemble-ai/chatterbox
- SadTalker: https://github.com/OpenTalker/SadTalker
- FFmpeg: https://ffmpeg.org/download.html
- uv: https://github.com/astral-sh/uv

Use your own recordings or recordings you have permission to use. The app creates a talking-video likeness, not a full 3D body, a memory/personality model, or an indistinguishable copy.

## Workspace improvements

Uploaded videos with audio automatically supply the normal voice reference when none exists. Existing voice samples are preserved. Photo and video portraits are retained separately and can be switched. Personas can be renamed. Upload processing no longer holds the global job lock, so cancellation remains responsive while another upload is converted.

Detail mode can exceed a 4 GB GPU's memory and automatically use CPU. Draft is recommended on GTX 1050 4 GB. Face inference now uses bounded CPU threading, and retry diagnostics are scoped to the current process instead of old log errors.
