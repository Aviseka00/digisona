"""Check an installation without requiring anyone's personal recordings."""
import json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['PATH']=str(ROOT / 'tools/bin')+os.pathsep+os.environ.get('PATH','')
os.environ['HF_HOME']=str(ROOT / 'models/huggingface')
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['TORCH_HOME']=str(ROOT / 'models/torch-cache')
def check(args,cwd=ROOT):
    subprocess.run([str(a) for a in args],cwd=cwd,check=True,timeout=3600)
if __name__=='__main__':
    cfg_path=ROOT / 'config.json'
    cfg=json.loads((cfg_path if cfg_path.exists() else ROOT / 'config.example.json').read_text(encoding='utf-8-sig'))
    voice=cfg.get('model_python') or ROOT / '.venv/Scripts/python.exe'
    face=cfg.get('sadtalker_python') or ROOT / '.venv-sad/Scripts/python.exe'
    sad=Path(cfg.get('sadtalker_path') or ROOT / 'models/SadTalker')
    check(['ffmpeg','-v','error','-version']);check(['ffprobe','-v','error','-version'])
    check([face,sad / 'inference.py','--help'],sad)
    check([face,'-c','import torch; from safetensors import safe_open; import sys; f=safe_open(sys.argv[1],framework="pt",device="cpu"); assert len(list(f.keys()))>0; print("Face checkpoint validated; CUDA available:",torch.cuda.is_available())',sad / 'checkpoints/SadTalker_V0.0.2_256.safetensors'])
    check([voice,'-c','import voice_worker,torch; torch.set_num_threads(4); model=voice_worker.load_model("cpu"); print("Pinned voice weights downloaded and model loaded")'])
    for python in (voice,face):check([python,'-m','pip','check'])
    (ROOT / 'models/setup-verified.json').write_text(json.dumps({'verified_at':time.time(),'kind':'installation','note':'Model loading and dependencies verified. Personal video quality is evaluated after capture.'}),encoding='utf-8')
    print('INSTALLATION VERIFIED. Run start.cmd, record your samples, and generate a short test.')
