"""Media validation, recording diagnostics and generation helpers."""
import array, json, math, re, subprocess
from pathlib import Path

def probe(path):
    result = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,timeout=30)
    if result.returncode: raise ValueError('This recording cannot be decoded. Record it again or choose a different file.')
    info = json.loads(result.stdout)
    duration = float(info.get('format',{}).get('duration',0) or 0)
    if duration <= 0:
        duration = max([float(s.get('duration',0) or 0) for s in info['streams']] or [0])
    return {'duration':round(duration,2),'streams':info['streams']}

def analyze_voice(path):
    result = subprocess.run(['ffmpeg','-v','error','-i',str(path),'-t','30','-ac','1','-ar','16000','-f','s16le','-'],capture_output=True,timeout=30)
    if result.returncode: raise ValueError('Could not decode this voice sample')
    samples = array.array('h'); samples.frombytes(result.stdout)
    if not samples: raise ValueError('No audio was found in this sample')
    rms = math.sqrt(sum(v*v for v in samples)/len(samples))/32768
    peak = max(abs(v) for v in samples)/32768
    clipped = sum(abs(v)>=32000 for v in samples)/len(samples)
    windows = [samples[i:i+320] for i in range(0,len(samples),320)]
    quiet = sum(math.sqrt(sum(v*v for v in w)/len(w))/32768 < .005 for w in windows)/len(windows)
    duration = len(samples)/16000
    warnings = []
    if duration < 8: warnings.append('Record at least 8 seconds of natural speech for a better voice reference.')
    if rms < .015: warnings.append('The average recording level is low. Move closer to the microphone.')
    if clipped > .005: warnings.append('Some audio is clipped. Reduce microphone gain or move slightly farther away.')
    if quiet > .65: warnings.append('Much of this sample is silence. Record more continuous speech.')
    return {'duration':round(duration,1),'level_db':round(20*math.log10(max(rms,1e-8)),1),'peak':round(peak,3),'silence_percent':round(quiet*100),'clipping_percent':round(clipped*100,2),'warnings':warnings,'summary':'Sample checks passed' if not warnings else 'Review this sample','note':'Level and silence checks are approximate; they do not measure speaker similarity or background noise.'}

def portrait(video, seconds, output):
    info = probe(video)
    if not any(s['codec_type']=='video' for s in info['streams']): raise ValueError('This file has no video stream')
    if info['duration'] and seconds >= info['duration']: raise ValueError('Select a frame before the end of the video')
    result = subprocess.run(['ffmpeg','-v','error','-y','-ss',str(seconds),'-i',str(video),'-frames:v','1',str(output)],capture_output=True,timeout=30)
    if result.returncode or not output.exists() or output.stat().st_size<100: raise ValueError('Could not extract that portrait frame. Select an earlier frame.')
    return info

def log_tail(path, size=12000):
    if not path.exists(): return ''
    with path.open('rb') as stream:
        stream.seek(max(0,path.stat().st_size-size)); return stream.read().decode('utf-8',errors='replace')

def render_progress(log):
    matches = re.findall(r'Face Renderer::\s*(\d+)%[^\r\n]*?\|\s*(\d+)/(\d+)',log)
    if not matches: return None
    percent, done, total = matches[-1]
    return {'percent':int(percent),'frames':int(done),'total':int(total)}

def failure_message(log):
    lower = log.lower()
    if 'out of memory' in lower: return 'GPU memory ran out. Retrying on CPU is available; it will be slower.'
    if "can't get the coeffs" in lower or 'no face' in lower: return 'A clear face could not be detected. Select a well-lit portrait with your mouth visible.'
    if 'certificate' in lower or 'connectionerror' in lower: return 'A model download connection failed. Check internet access and retry.'
    if 'no module named' in lower: return 'A model dependency is missing. Repair setup using setup.ps1.'
    return 'Processing failed. Open diagnostics for details, then retry the job.'

def split_script(text, limit=180):
    """Keep CPU speech synthesis bounded, preserving punctuation and all words."""
    chunks=[]; current=''
    for word in text.split():
        if current and len(current)+len(word)+1>limit: chunks.append(current); current=''
        current = (current+' '+word).strip()
        if len(current)>60 and re.search(r'[.!?]$',word): chunks.append(current); current=''
    if current: chunks.append(current)
    return chunks
