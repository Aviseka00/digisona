"""Local-only persona studio. Python 3.11, standard library web server."""
import json, os, re, shutil, socket, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import studio
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
os.environ['PATH'] = str(ROOT / 'tools' / 'bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['HF_HOME'] = str(ROOT / 'models' / 'huggingface')
os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['TORCH_HOME'] = str(ROOT / 'models' / 'torch-cache')
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
JOBS = DATA / 'jobs'
JOBS.mkdir(exist_ok=True)
LOCK = threading.RLock()
UPLOAD_LOCK=threading.Lock()
UPLOADING=set()
@contextmanager
def uploading(pid):
    with UPLOAD_LOCK:
        with LOCK: UPLOADING.add(pid)
        try:yield
        finally:
            with LOCK:UPLOADING.discard(pid)
CANCEL = set()
ACTIVE = {}
MAX_UPLOAD = 100 * 1024 * 1024
ID = re.compile(r'^[a-f0-9]{32}$')

def save_json(p, value):
    with LOCK:
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
        tmp.replace(p)

def read_json(p):
    return json.loads(p.read_text(encoding='utf-8'))

def profile_dir(pid):
    if not ID.fullmatch(pid): raise ValueError('Invalid profile ID')
    p = DATA / pid
    if not (p / 'profile.json').exists(): raise ValueError('Profile not found')
    return p

def job_path(jid):
    if not ID.fullmatch(jid): raise ValueError('Invalid job ID')
    return JOBS / (jid + '.json')

def status():
    config = read_json(ROOT / ('config.json' if (ROOT / 'config.json').exists() else 'config.example.json'))
    py = Path(config['model_python']) if config.get('model_python') else ROOT / '.venv' / 'Scripts' / 'python.exe'
    sad = Path(config.get('sadtalker_path') or ROOT / 'models' / 'SadTalker')
    ff = shutil.which('ffmpeg')
    fp = shutil.which('ffprobe')
    checkpoints = all((sad / 'checkpoints' / name).is_file() for name in ('SadTalker_V0.0.2_256.safetensors','mapping_00229-model.pth.tar'))
    sadpy = Path(config.get('sadtalker_python') or ROOT / '.venv-sad/Scripts/python.exe')
    verified = (ROOT / 'models' / 'setup-verified.json').is_file()
    ready = bool(verified and py.exists() and sadpy.exists() and ff and fp and (sad / 'inference.py').exists() and checkpoints)
    return {'ready': ready, 'engines_verified': verified, 'python': str(py), 'python_found': py.exists() and sadpy.exists(), 'ffmpeg': bool(ff), 'ffprobe': bool(fp), 'sadtalker_found': (sad / 'inference.py').exists(), 'checkpoints_found': checkpoints, 'free_gb': round(shutil.disk_usage(DATA).free / 1024**3, 1), 'note': 'Generation requires a successful setup verification. Models and caches are stored in this app folder.'}, config, py, sad

def run(jid, args, cwd=None):
    if jid in CANCEL: raise RuntimeError('Cancelled')
    log = JOBS / (jid + '.log')
    log_start=log.stat().st_size if log.exists() else 0
    update(jid,process_log_start=log_start)
    with log.open('ab') as out:
        proc = subprocess.Popen(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        with LOCK: ACTIVE[jid] = proc
        try:
            start = time.monotonic()
            while proc.poll() is None:
                if jid in CANCEL or time.monotonic() - start > 3600:
                    stop_process(proc)
                    raise RuntimeError('Cancelled' if jid in CANCEL else 'Model exceeded one hour timeout')
                time.sleep(.3)
            if jid in CANCEL: raise RuntimeError('Cancelled')
            if proc.returncode:
                raise RuntimeError(studio.failure_message(studio.log_tail(log,start=log_start)))
        finally:
            with LOCK: ACTIVE.pop(jid, None)

def stop_process(proc):
    if proc.poll() is not None: return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=15)
    else: proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()

def update(jid, **kw):
    with LOCK:
        p = job_path(jid)
        j = read_json(p)
        j.update(kw)
        j['updated'] = time.time()
        save_json(p, j)

def all_jobs():
    return [read_json(p) for p in JOBS.glob('*.json')]

def queue_room():
    if sum(j['state'] in ('queued','running') for j in all_jobs()) >= 4:
        raise ValueError('The queue is full. Wait for a job or cancel one first.')

def enqueue(obj):
    p = profile_dir(obj.get('profile',''))
    tone = obj.get('tone','normal')
    kind = obj.get('kind','video')
    composition = obj.get('composition','portrait')
    quality=obj.get('quality','draft')
    if quality not in ('draft','detail'):raise ValueError('Choose draft or detail quality')
    script = str(obj.get('script','')).strip()
    if tone not in ('normal','happy','calm','serious'): raise ValueError('Invalid voice tone')
    if kind not in ('voice','video'): raise ValueError('Invalid job type')
    if composition not in ('portrait','full'): raise ValueError('Invalid composition')
    if not 1 <= len(script) <= 1200: raise ValueError('Use 1–1200 characters. Short sentences are best for the first test.')
    if quality=='detail' and len(script)>240:raise ValueError('Detail mode supports up to 240 characters to limit memory use. Choose Draft for longer scripts.')
    speed = float(obj.get('speed',1)); expression = float(obj.get('expression',.5))
    if not .75 <= speed <= 1.25 or not 0 <= expression <= 1: raise ValueError('Speed or expression is outside the supported range')
    pronunciations = obj.get('pronunciations','')
    spoken = script
    for line in str(pronunciations).splitlines()[:20]:
        if '=' not in line: continue
        original, replacement = [part.strip() for part in line.split('=',1)]
        if original and replacement:
            spoken = re.sub(r'(?<!\w)'+re.escape(original)+r'(?!\w)',lambda _:replacement,spoken,flags=re.I)
    if len(spoken)>1600: raise ValueError('Pronunciation substitutions made the script too long')
    if not (p / ('voice-'+tone+'.webm')).exists(): raise ValueError('Record or import the selected voice tone first')
    if kind=='video' and not ((p / 'portrait.png').exists() or (p / 'face.webm').exists()): raise ValueError('Upload a photo or record/import a face video first')
    info,cfg,py,sad=status()
    if not info['ready']: raise ValueError('Complete local model setup first')
    if composition=='full' and not (sad / 'checkpoints/mapping_00109-model.pth.tar').exists(): raise ValueError('Full-frame checkpoint is not installed yet; choose portrait')
    if info['free_gb']<2: raise ValueError('At least 2 GB free disk space is required')
    if quality=='detail' and not (sad / 'checkpoints/SadTalker_V0.0.2_512.safetensors').exists():raise ValueError('Install the 512-pixel model using install.cmd before selecting detail mode')
    with LOCK:
        if obj['profile'] in UPLOADING: raise ValueError('Your upload is still processing. Wait for it to finish before generating.')
        queue_room()
        jid=uuid.uuid4().hex; work=JOBS / jid; work.mkdir()
        profile=read_json(p / 'profile.json')
        shutil.copy2(p / ('voice-'+tone+'.webm'),work / 'reference.webm')
        if (p / 'face.webm').exists(): shutil.copy2(p / 'face.webm',work / 'face.webm')
        if (p / 'portrait.png').exists(): shutil.copy2(p / 'portrait.png',work / 'face.png')
        j={'id':jid,'profile':obj['profile'],'profile_name':profile['name'],'tone':tone,'script':script,'spoken_script':spoken,'kind':kind,'speed':speed,'expression':expression,'composition':composition,'portrait_seconds':profile.get('portrait_seconds',0),'created':time.time(),'state':'queued','stage':'Waiting in queue','step':'queued','attempts':0}
        j['quality']=quality;save_json(job_path(jid),j)
    return j

def worker():
    while True:
        with LOCK:
            pending = all_jobs()
            pending = sorted([j for j in pending if j['state'] == 'queued'], key=lambda j: j['created'])
            if pending:
                j=pending[0]
                update(j['id'],state='running',stage='Preparing recordings',step='prepare',started=time.time(),attempts=j.get('attempts',0)+1)
        if not pending: time.sleep(1); continue
        jid = j['id']
        work = JOBS / jid
        work.mkdir(exist_ok=True)
        try:
            if jid in CANCEL: raise RuntimeError('Cancelled')
            info, cfg, py, sad = status()
            if not info['ready']: raise RuntimeError('Setup incomplete. Open Setup and install the required local models.')
            if info['free_gb'] < 2: raise RuntimeError('At least 2 GB free disk space is required')
            p = profile_dir(j['profile'])
            # Legacy jobs may not have immutable snapshots yet.
            if not (work / 'reference.webm').exists(): shutil.copy2(p / ('voice-'+j['tone']+'.webm'),work / 'reference.webm')
            if not (work / 'face.webm').exists() and (p / 'face.webm').exists(): shutil.copy2(p / 'face.webm',work / 'face.webm')
            if not (work / 'reference.wav').exists():
                run(jid, ['ffmpeg','-y','-i',str(work / 'reference.webm'),'-t','30','-ac','1','-ar','24000',str(work / 'reference.wav')])
            if (work / 'base-speech.wav').exists():
                try: studio.probe(work / 'base-speech.wav')
                except ValueError: (work / 'base-speech.wav').unlink()
            if not (work / 'base-speech.wav').exists():
                update(jid, stage='Generating your voice on CPU',step='voice')
                script = work / 'script.txt'; script.write_text(j.get('spoken_script',j['script']), encoding='utf-8')
                run(jid, [str(py),str(ROOT / 'voice_worker.py'),'--text',str(script),'--reference',str(work / 'reference.wav'),'--output',str(work / 'base-speech.wav'),'--device',cfg.get('voice_device','cpu'),'--exaggeration',str(j.get('expression',.5))])
            run(jid,['ffmpeg','-y','-i',str(work / 'base-speech.wav'),'-af','atempo='+str(j.get('speed',1))+',apad=whole_dur=0.2',str(work / 'speech.wav')])
            audio_url='/media/jobs/'+jid+'/speech.wav'
            update(jid,audio=audio_url,duration=studio.probe(work / 'speech.wav')['duration'])
            if j.get('kind')=='voice':
                update(jid,state='preview',stage='Voice ready. Listen, then render your video.',step='preview',completed=time.time())
                continue
            if not (work / 'face.png').exists():
                run(jid, ['ffmpeg','-y','-ss',str(j.get('portrait_seconds',0)),'-i',str(work / 'face.webm'),'-frames:v','1',str(work / 'face.png')])
            update(jid, stage='Animating your face',step='render')
            sadpy = cfg.get('sadtalker_python') or str(ROOT / '.venv-sad/Scripts/python.exe')
            args=[sadpy,str(ROOT / 'face_worker.py'),str(sad / 'inference.py'),'--driven_audio',str(work / 'speech.wav'),'--source_image',str(work / 'face.png'),'--result_dir',str(work / 'render'),'--size','512' if j.get('quality')=='detail' else '256','--batch_size','1','--preprocess','full' if j.get('composition')=='full' else 'crop','--still']
            if j.get('cpu_render') or cfg.get('render_device')=='cpu': args.append('--cpu')
            try: run(jid,args,cwd=str(sad))
            except RuntimeError as error:
                if jid in CANCEL or '--cpu' in args or 'GPU memory ran out' not in str(error): raise
                update(jid,stage='GPU memory was full. Rendering on CPU.',warning='Automatic CPU fallback is slower.',cpu_render=True)
                run(jid,args+['--cpu'],cwd=str(sad))
            videos = list((work / 'render').rglob('*.mp4'))
            if not videos: raise RuntimeError('Video model did not produce an MP4')
            source = max(videos, key=lambda p: p.stat().st_mtime)
            update(jid, stage='Finishing your MP4',step='encode')
            run(jid, ['ffmpeg','-y','-i',str(source),'-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(work / 'output.mp4')])
            if not (work / 'output.mp4').stat().st_size: raise RuntimeError('Empty output video')
            studio.probe(work / 'output.mp4')
            update(jid, state='done', step='done',stage='Video ready',completed=time.time(),output='/media/jobs/' + jid + '/output.mp4')
        except Exception as exc:
            update(jid, state='cancelled' if jid in CANCEL else 'failed', stage=str(exc),completed=time.time())
        finally:
            CANCEL.discard(jid)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, value, code=200):
        data = json.dumps(value).encode()
        self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def guard(self):
        if self.headers.get('Host') not in ('127.0.0.1:8765','localhost:8765'): raise ValueError('Invalid local host')
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765'): raise ValueError('Only the local app may access this server')
    def body(self, maximum=16384):
        n = int(self.headers.get('Content-Length','0'))
        if n <= 0 or n > maximum: raise ValueError('Invalid request size')
        data = self.rfile.read(n)
        if len(data) != n: raise ValueError('Incomplete upload')
        return data
    def do_GET(self):
        try:
            self.guard(); route = urlparse(self.path).path
            if route == '/api/status': return self.send(status()[0])
            if route == '/api/profiles':
                return self.send([read_json(p) for p in DATA.glob('*/profile.json')])
            if route == '/api/jobs':
                jobs=all_jobs()
                for j in jobs:
                    if j['state']=='running' and j.get('step')=='render':
                        j['progress']=studio.render_progress(studio.log_tail(JOBS / (j['id']+'.log'),start=j.get('process_log_start',0)))
                return self.send(sorted(jobs,key=lambda j:j['created'],reverse=True))
            if route.startswith('/api/log/'):
                p = job_path(route.rsplit('/',1)[-1]).with_suffix('.log')
                return self.send({'log':studio.log_tail(p)})
            if route.startswith('/media/'):
                p = (DATA / route[len('/media/'):]).resolve()
                if not p.is_relative_to(DATA.resolve()): raise ValueError('Invalid media path')
            else:
                p = ROOT / 'web' / ('index.html' if route == '/' else route.lstrip('/'))
                p = p.resolve()
                if not p.is_relative_to((ROOT / 'web').resolve()): raise ValueError('Invalid path')
            if not p.is_file(): return self.send({'error':'Not found'},404)
            import mimetypes
            size = p.stat().st_size; start = 0; end = size - 1
            range_header = self.headers.get('Range','')
            m = re.fullmatch(r'bytes=(\d+)-(\d*)',range_header)
            if m:
                start = int(m[1]); end = min(int(m[2]) if m[2] else end,end)
                if start > end: return self.send({'error':'Invalid range'},416)
            self.send_response(206 if m else 200)
            self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(end-start+1)); self.send_header('Accept-Ranges','bytes')
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            if m: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            with p.open('rb') as f:
                f.seek(start); remaining = end-start+1
                while remaining:
                    chunk = f.read(min(65536,remaining))
                    if not chunk: break
                    self.wfile.write(chunk); remaining -= len(chunk)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
        except Exception as exc: self.send({'error':str(exc)},400)
    def do_POST(self):
        try:
            self.guard(); route = urlparse(self.path).path
            if route.startswith('/api/upload/'):
                _,_,_,pid,kind = route.split('/')
                if kind not in ('face','photo','voice-normal','voice-happy','voice-calm','voice-serious'): raise ValueError('Invalid recording type')
                p = profile_dir(pid)
                blob = self.body(MAX_UPLOAD)
                with uploading(pid):
                    if any(read_json(q)['profile'] == pid and read_json(q)['state'] in ('queued','running') for q in JOBS.glob('*.json')):
                        raise ValueError('Wait for generation to finish before replacing this persona recording')
                    if kind=='photo':
                        if len(blob)>20*1024*1024: raise ValueError('Photos must be smaller than 20 MB')
                        tmp=p / 'photo.upload'; converted=p / 'photo.converted.png'; tmp.write_bytes(blob)
                        try:
                            info=studio.probe(tmp)
                            tracks=[s for s in info['streams'] if s['codec_type']=='video']
                            if not tracks or tracks[0].get('codec_name') not in ('png','mjpeg','webp'): raise ValueError('Choose a JPEG, PNG or WebP photo')
                            if tracks[0].get('width',0)*tracks[0].get('height',0)>30_000_000: raise ValueError('Choose a photo smaller than 30 megapixels')
                            result=subprocess.run(['ffmpeg','-v','error','-y','-i',str(tmp),'-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-frames:v','1',str(converted)],capture_output=True,timeout=30)
                            if result.returncode or not converted.exists(): raise ValueError('This photo could not be decoded')
                            converted.replace(p / 'portrait.png')
                            shutil.copy2(p / 'portrait.png',p / 'photo.png')
                        finally:
                            tmp.unlink(missing_ok=True); converted.unlink(missing_ok=True)
                        profile=read_json(p / 'profile.json'); profile.update(face_source='photo',portrait='/media/'+pid+'/portrait.png',updated=time.time())
                        profile['samples']['photo']=profile['portrait']; save_json(p / 'profile.json',profile)
                        return self.send(profile)
                    dest = p / (kind + '.webm'); tmp = p / (kind + '.upload'); tmp.write_bytes(blob)
                    try:
                        info=studio.probe(tmp)
                        expected='video' if kind=='face' else 'audio'
                        if not any(s['codec_type']==expected for s in info['streams']): raise ValueError('This file has no '+expected+' track')
                        if info['duration']>90: raise ValueError('Choose a recording shorter than 90 seconds')
                        converted=p / (kind+'.converted.webm')
                        args=['ffmpeg','-v','error','-y','-i',str(tmp),'-t','20' if kind=='face' else '30']
                        if kind=='face': args+=['-an','-c:v','libvpx','-deadline','realtime','-cpu-used','5','-b:v','2M','-threads','4']
                        else: args+=['-vn','-c:a','libopus','-b:a','128k']
                        result=subprocess.run(args+[str(converted)],capture_output=True,timeout=180)
                        if result.returncode: raise ValueError('Recording conversion failed. Try a different file.')
                        converted.replace(dest)
                        if kind=='face' and not (p / 'voice-normal.webm').exists() and any(s['codec_type']=='audio' for s in info['streams']):
                            extracted=p / 'video-voice.webm'
                            audio=subprocess.run(['ffmpeg','-v','error','-y','-i',str(tmp),'-t','30','-vn','-c:a','libopus','-b:a','128k',str(extracted)],capture_output=True,timeout=60)
                            if audio.returncode==0:extracted.replace(p / 'voice-normal.webm')
                    finally: tmp.unlink(missing_ok=True)
                    profile = read_json(p / 'profile.json')
                    profile['updated']=time.time()
                    profile['samples'][kind] = '/media/' + pid + '/' + kind + '.webm'
                    if kind == 'face':
                        profile['face_source']='video'
                        profile['portrait_seconds'] = 0
                        studio.portrait(dest,0,p / 'portrait.png')
                        shutil.copy2(p / 'portrait.png',p / 'video-portrait.png')
                        profile['portrait']='/media/'+pid+'/portrait.png'
                        if (p / 'voice-normal.webm').exists():
                            profile['samples']['voice-normal']='/media/'+pid+'/voice-normal.webm'
                    else:
                        profile.setdefault('analysis',{})[kind]=studio.analyze_voice(dest)
                    save_json(p / 'profile.json',profile)
                return self.send(profile)
            obj = json.loads(self.body())
            if route == '/api/rename-profile':
                p=profile_dir(obj.get('id',''));name=str(obj.get('name','')).strip()[:80]
                if not name:raise ValueError('Enter a persona name')
                with LOCK:
                    profile=read_json(p / 'profile.json');profile.update(name=name,updated=time.time());save_json(p / 'profile.json',profile)
                return self.send(profile)
            if route == '/api/face-source':
                pid=obj.get('profile','');p=profile_dir(pid);source=obj.get('source')
                if source not in ('photo','video'):raise ValueError('Choose photo or video')
                with LOCK:
                    if pid in UPLOADING:raise ValueError('Wait for your upload to finish')
                    selected=p / ('photo.png' if source=='photo' else 'video-portrait.png')
                    if not selected.exists():
                        profile=read_json(p / 'profile.json')
                        if source=='photo' and profile.get('face_source')=='photo':shutil.copy2(p / 'portrait.png',selected)
                        elif source=='video' and (p / 'face.webm').exists():studio.portrait(p / 'face.webm',float(profile.get('portrait_seconds',0)),selected)
                        else:raise ValueError('Upload this source first')
                    shutil.copy2(selected,p / 'portrait.png');profile=read_json(p / 'profile.json');profile.update(face_source=source,portrait='/media/'+pid+'/portrait.png',updated=time.time());save_json(p / 'profile.json',profile)
                return self.send(profile)
            if route == '/api/profiles':
                name = str(obj.get('name','')).strip()[:80]
                if not name: raise ValueError('Enter a profile name')
                pid = uuid.uuid4().hex; p = DATA / pid; p.mkdir()
                profile = {'id':pid,'name':name,'samples':{},'created':time.time()}; save_json(p / 'profile.json',profile)
                return self.send(profile,201)
            if route == '/api/select-frame':
                p = profile_dir(obj.get('profile',''))
                seconds = float(obj.get('seconds',0))
                if not 0 <= seconds <= 20: raise ValueError('Select a frame between 0 and 20 seconds')
                with LOCK:
                    studio.portrait(p / 'face.webm',seconds,p / 'portrait.png')
                    profile = read_json(p / 'profile.json')
                    profile['portrait_seconds'] = seconds
                    profile['face_source']='video'
                    shutil.copy2(p / 'portrait.png',p / 'video-portrait.png')
                    profile['updated']=time.time()
                    profile['portrait']='/media/'+obj['profile']+'/portrait.png'
                    save_json(p / 'profile.json',profile)
                return self.send(profile)
            if route == '/api/analyze':
                p=profile_dir(obj.get('profile','')); tone=obj.get('tone','normal')
                if tone not in ('normal','happy','calm','serious'): raise ValueError('Invalid tone')
                result=studio.analyze_voice(p / ('voice-'+tone+'.webm'))
                with LOCK:
                    profile=read_json(p / 'profile.json'); profile.setdefault('analysis',{})['voice-'+tone]=result; save_json(p / 'profile.json',profile)
                return self.send(result)
            if route == '/api/generate':
                return self.send(enqueue(obj),201)
            if route in ('/api/render','/api/retry'):
                jid=obj.get('id','')
                with LOCK:
                    queue_room(); j=read_json(job_path(jid)); work=JOBS / jid
                    allowed=('preview',) if route=='/api/render' else ('failed','cancelled','interrupted')
                    if j['state'] not in allowed: raise ValueError('This job cannot be started in its current state')
                    if route=='/api/render':
                        if not ((work / 'face.png').exists() or (work / 'face.webm').exists()): raise ValueError('Upload a photo or record a face video, then create a new voice preview')
                        j['kind']='video'
                    if obj.get('cpu'): j['cpu_render']=True
                    j.update(state='queued',stage='Waiting in queue',step='queued',progress=None,updated=time.time())
                    save_json(job_path(jid),j)
                return self.send(j)
            if route == '/api/delete-job':
                jid=obj.get('id','')
                with LOCK:
                    j=read_json(job_path(jid))
                    if j['state'] in ('queued','running'): raise ValueError('Cancel the job before deleting it')
                    work=(JOBS / jid).resolve()
                    if not work.is_relative_to(JOBS.resolve()): raise ValueError('Invalid job folder')
                    if work.exists(): shutil.rmtree(work)
                    job_path(jid).unlink(); job_path(jid).with_suffix('.log').unlink(missing_ok=True)
                return self.send({'ok':True})
            if route == '/api/cancel':
                jid = obj['id']
                with LOCK:
                    j = read_json(job_path(jid))
                    if j['state'] == 'queued': update(jid,state='cancelled',stage='Cancelled')
                    elif j['state'] == 'running': CANCEL.add(jid)
                return self.send({'ok':True})
            if route == '/api/delete-profile':
                p = profile_dir(obj['id'])
                with LOCK:
                    if obj['id'] in UPLOADING:raise ValueError('Wait for your upload to finish before deleting the persona')
                    related = [read_json(q) for q in JOBS.glob('*.json') if read_json(q)['profile'] == obj['id']]
                    if any(j['state'] in ('queued','running') for j in related): raise ValueError('Cancel the active job and wait for it to stop before deleting')
                    shutil.rmtree(p)
                    for j in related:
                        work = JOBS / j['id']
                        if work.exists(): shutil.rmtree(work)
                        job_path(j['id']).unlink(missing_ok=True); job_path(j['id']).with_suffix('.log').unlink(missing_ok=True)
                return self.send({'ok':True})
            self.send({'error':'Not found'},404)
        except Exception as exc: self.send({'error':str(exc)},400)

class LocalServer(ThreadingHTTPServer):
    allow_reuse_address=False
    daemon_threads=True
    def server_bind(self):
        if os.name=='nt': self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

if __name__ == '__main__':
    try: local_server=LocalServer(('127.0.0.1',8765),Handler)
    except OSError:
        print('Port 8765 is already in use. If Persona Studio is running, open http://127.0.0.1:8765 instead of starting another server.',flush=True)
        sys.exit(1)
    for p in JOBS.glob('*.json'):
        j = read_json(p)
        if j['state'] in ('queued','running'):
            j.update(state='interrupted',stage='Server restarted. Retry to continue using completed speech.'); save_json(p,j)
    threading.Thread(target=worker,daemon=True).start()
    print('Persona Studio: http://127.0.0.1:8765 — Ctrl+C to stop',flush=True)
    try:local_server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        with LOCK:
            processes=list(ACTIVE.values()); CANCEL.update(ACTIVE)
        for proc in processes:stop_process(proc)
        local_server.server_close()
