"""Run a short real voice-and-face generation before marking setup ready."""
import json, os, subprocess, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ['PATH'] = str(ROOT / 'tools/bin') + os.pathsep + os.environ.get('PATH','')
os.environ['HF_HOME'] = str(ROOT / 'models/huggingface')
os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['TORCH_HOME'] = str(ROOT / 'models/torch-cache')
work = ROOT / 'data/setup-test'
work.mkdir(parents=True,exist_ok=True)
cfg = json.loads((ROOT / ('config.json' if (ROOT / 'config.json').exists() else 'config.example.json')).read_text())
voice = cfg.get('model_python') or str(ROOT / '.venv/Scripts/python.exe')
sadpython = cfg.get('sadtalker_python') or str(ROOT / '.venv-sad/Scripts/python.exe')
sad = Path(cfg.get('sadtalker_path') or ROOT / 'models/SadTalker')

def run(args, cwd=ROOT):
    print('Running: ' + Path(args[0]).name + ' ' + str(args[1]),flush=True)
    with (work / 'verification.log').open('ab') as log:
        proc = subprocess.run(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    if proc.returncode:
        raise RuntimeError('Verification failed. Read data/setup-test/verification.log')

if __name__ == '__main__':
    run([voice,'-c','from chatterbox.tts import ChatterboxTTS; print("voice import OK")'])
    run([sadpython,str(sad / 'inference.py'),'--help'],sad)
    profiles = [p for p in (ROOT / 'data').iterdir() if (p / 'face.webm').exists() and (p / 'voice-normal.webm').exists()]
    if not profiles: raise RuntimeError('Record face and normal voice samples first, then rerun verification')
    p = profiles[0]
    frame_time = float(json.loads((p / 'profile.json').read_text()).get('portrait_seconds',0))
    run(['ffmpeg','-y','-ss',str(frame_time),'-i',str(p / 'face.webm'),'-frames:v','1',str(work / 'face.png')])
    run(['ffmpeg','-y','-i',str(p / 'voice-normal.webm'),'-t','15','-ac','1','-ar','24000',str(work / 'reference.wav')])
    (work / 'script.txt').write_text('Hello. This is my digital persona.',encoding='utf-8')
    run([voice,str(ROOT / 'voice_worker.py'),'--text',str(work / 'script.txt'),'--reference',str(work / 'reference.wav'),'--output',str(work / 'speech.wav'),'--device','cpu'])
    run([sadpython,str(sad / 'inference.py'),'--driven_audio',str(work / 'speech.wav'),'--source_image',str(work / 'face.png'),'--result_dir',str(work / 'render'),'--size','256','--batch_size','1','--preprocess','crop','--still'],sad)
    outputs = list((work / 'render').rglob('*.mp4'))
    if not outputs: raise RuntimeError('No test video was generated')
    source = max(outputs,key=lambda p:p.stat().st_mtime)
    output = ROOT / 'data/setup-preview.mp4'
    run(['ffmpeg','-y','-i',str(source),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(output)])
    run(['ffprobe','-v','error','-show_entries','format=duration',str(output)])
    (ROOT / 'models/setup-verified.json').write_text(json.dumps({'verified_at':time.time(),'preview':'/media/setup-preview.mp4'}),encoding='utf-8')
    print('SETUP VERIFIED. Preview: http://127.0.0.1:8765/media/setup-preview.mp4',flush=True)
