"""Download upstream model checkpoints and a local Windows FFmpeg build."""
from pathlib import Path
from urllib.request import urlopen, Request
import concurrent.futures, hashlib, json, shutil, time, zipfile
ROOT = Path(__file__).resolve().parent
CHECKSUMS=json.loads((ROOT / 'asset-checksums.json').read_text(encoding='utf-8'))
def valid(path):
    if not path.exists() or path.stat().st_size<=1024: return False
    expected=CHECKSUMS.get(path.name)
    if not expected:return True
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()==expected

def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if valid(dest): return
    temp = dest.with_suffix(dest.suffix + '.partial')
    print('Downloading ' + dest.name, flush=True)
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'Digisona/1.0'}),timeout=120) as response, temp.open('wb') as out:
                expected_size=response.headers.get('Content-Length')
                shutil.copyfileobj(response,out)
            if expected_size and temp.stat().st_size!=int(expected_size):raise RuntimeError('Incomplete download: '+dest.name)
            expected_hash=CHECKSUMS.get(dest.name)
            if expected_hash:
                with temp.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=expected_hash:raise RuntimeError('Checksum mismatch: '+dest.name)
            temp.replace(dest);break
        except Exception:
            if attempt==2:raise
            time.sleep(2)
    print('Saved ' + dest.name,flush=True)

if __name__ == '__main__':
    base = 'https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/'
    sad = ROOT / 'models' / 'SadTalker'
    assets = [(base + name,sad / 'checkpoints' / name) for name in ['mapping_00229-model.pth.tar','mapping_00109-model.pth.tar','SadTalker_V0.0.2_256.safetensors']]
    assets += [('https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth',sad / 'gfpgan/weights/detection_Resnet50_Final.pth'),('https://github.com/xinntao/facexlib/releases/download/v0.1.0/alignment_WFLW_4HG.pth',sad / 'gfpgan/weights/alignment_WFLW_4HG.pth')]
    archive = ROOT / 'tools' / 'ffmpeg.zip'
    assets.append(('https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',archive))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda pair: download(*pair),assets): pass
    target = ROOT / 'tools' / 'bin'; target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            if member.endswith(('/ffmpeg.exe','/ffprobe.exe')):
                with bundle.open(member) as source, (target / Path(member).name).open('wb') as out: shutil.copyfileobj(source,out)
            elif Path(member).name.lower().startswith('license'):
                notices=ROOT / 'tools/notices/ffmpeg';notices.mkdir(parents=True,exist_ok=True)
                with bundle.open(member) as source,(notices / Path(member).name).open('wb') as out:shutil.copyfileobj(source,out)
    print('Assets ready',flush=True)
