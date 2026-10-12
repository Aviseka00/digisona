# Third-party notices

The MIT license in LICENSE applies to Digisona's application code. Third-party software and model assets are downloaded separately and are not included in the source ZIP.

| Component | Project / license | Downloaded by |
|---|---|---|
| Chatterbox 0.1.7 | Resemble AI, MIT; model card: https://huggingface.co/ResembleAI/chatterbox | pip and verify_install.py |
| SadTalker source | OpenTalker, Apache 2.0, commit cd4c0465ae0b54a6f85af57f5c65fec9fe23e7f8 | setup.ps1 |
| SadTalker 256 model and mapping weights | Upstream release assets; review the upstream project and asset terms | download_assets.py |
| Facexlib models and dependencies | https://github.com/xinntao/facexlib; retain upstream licenses and asset terms | pip and download_assets.py |
| GFPGAN dependency | https://github.com/TencentARC/GFPGAN; upstream Apache 2.0 project | pip |
| FFmpeg Windows GPL build | BtbN build, GPL configuration: https://github.com/BtbN/FFmpeg-Builds | download_assets.py |
| uv 0.13.0 | Astral, MIT or Apache 2.0 | setup.ps1 |
| Managed Python runtimes | Python Software Foundation and python-build-standalone component notices | uv |
| PyTorch, torchvision, torchaudio and other Python dependencies | Each retains its own upstream license | pip |

The download helpers preserve third-party distribution notices where supplied. Check upstream licenses before redistribution or commercial use of model assets. Generated speech includes Chatterbox's upstream audio watermarking behavior.
