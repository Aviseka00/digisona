import argparse
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ.setdefault('HF_HOME', str(ROOT / 'models' / 'huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
VOICE_REVISION='5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18'

def load_model(device='cpu'):
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    from chatterbox.tts import ChatterboxTTS
    options={'repo_id':'ResembleAI/chatterbox','revision':VOICE_REVISION,'allow_patterns':['ve.safetensors','t3_cfg.safetensors','s3gen.safetensors','tokenizer.json','conds.pt']}
    try: directory=snapshot_download(**options,local_files_only=True)
    except LocalEntryNotFoundError:directory=snapshot_download(**options)
    return ChatterboxTTS.from_local(Path(directory),device=device)

def main():
    parser = argparse.ArgumentParser()
    for name in ('text','reference','output'): parser.add_argument('--' + name,required=True)
    parser.add_argument('--device',default='cpu',choices=['cpu','cuda'])
    parser.add_argument('--exaggeration',type=float,default=.5)
    parser.add_argument('--guidance',type=float,default=.5)
    parser.add_argument('--seed',type=int,default=42)
    args = parser.parse_args()
    import torchaudio
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    import random, numpy as np
    random.seed(args.seed); np.random.seed(args.seed)
    model = load_model(args.device)
    from studio import split_script
    segments = split_script(Path(args.text).read_text(encoding='utf-8'))
    clips=[]
    for index, segment in enumerate(segments):
        print(f'VOICE_SEGMENT {index+1}/{len(segments)}',flush=True)
        clip = model.generate(segment,audio_prompt_path=args.reference,exaggeration=args.exaggeration,cfg_weight=args.guidance)
        if clips: clips.append(torch.zeros((1,int(model.sr*.12))))
        clips.append(clip.cpu())
    speech = torch.cat(clips,dim=-1)
    destination=Path(args.output)
    temporary=destination.with_suffix('.pending.wav')
    torchaudio.save(str(temporary),speech.cpu(),model.sr)
    temporary.replace(destination)

if __name__ == '__main__': main()
