import os,sys,tempfile,subprocess
from pathlib import Path
with tempfile.TemporaryDirectory(prefix='pfi-test-') as d:
    env=dict(os.environ,PFI_DB=str(Path(d)/'test.db'))
    sys.exit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=Path(__file__).resolve().parent,env=env))
