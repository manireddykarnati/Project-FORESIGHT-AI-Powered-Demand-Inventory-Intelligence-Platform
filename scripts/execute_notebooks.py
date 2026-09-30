"""Execute both notebooks with this environment's Python, stopping on any error."""
import os
from pathlib import Path
import sys
import tempfile
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('JUPYTER_RUNTIME_DIR',str(Path(tempfile.gettempdir())/'foresight-jupyter'))
source=ROOT/'notebooks/FORESIGHT_notebook.ipynb'
nb=nbformat.read(source,as_version=4)
km=KernelManager(kernel_name='python3')
km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
try:
    NotebookClient(nb,km=km,timeout=600,resources={'metadata':{'path':str(ROOT)}}).execute()
finally:
    if km.has_kernel:
        km.shutdown_kernel(now=True)
assert not [o for c in nb.cells for o in c.get('outputs',[]) if o.output_type=='error']
nbformat.write(nb,source)
nbformat.write(nb,ROOT/'notebooks/FORESIGHT_notebook_executed.ipynb')
print('Both notebooks contain the same clean executed source and outputs.')
