"""Run the face engine with bounded CPU threading on modest computers."""
import os,runpy,sys
from pathlib import Path
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('MKL_NUM_THREADS','4')
if __name__=='__main__':
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(2)
    engine=Path(sys.argv[1]).resolve()
    sys.path.insert(0,str(engine.parent))
    # Upstream accumulates generated predictions before stacking them. Keep
    # finished inference frames on CPU instead of retaining the entire video
    # on a small GPU. Rendering calculations still use the selected device.
    from src.facerender.modules.generator import OcclusionAwareGenerator,OcclusionAwareSPADEGenerator
    def bounded_forward(original):
        def forward(self,*args,**kwargs):
            output=original(self,*args,**kwargs)
            if not self.training and 'prediction' in output:
                output['prediction']=output['prediction'].detach().cpu()
            return output
        return forward
    for generator in (OcclusionAwareGenerator,OcclusionAwareSPADEGenerator):
        generator.forward=bounded_forward(generator.forward)
    sys.argv=[str(engine),*sys.argv[2:]]
    runpy.run_path(str(engine),run_name='__main__')
