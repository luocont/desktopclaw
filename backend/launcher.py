import os
import sys
import subprocess

exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
litellm_dir = os.path.join(exe_dir, '_internal', 'litellm')
json_file = os.path.join(litellm_dir, 'model_prices_and_context_window_backup.json')

if os.path.exists(json_file):
    try:
        subprocess.run(['icacls', json_file, '/grant', 'Everyone:F'], 
                      check=True, capture_output=True)
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(exe_dir))
from start_server import main
import asyncio
asyncio.run(main())
