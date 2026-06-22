import os
import stat
import sys

exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

for root, dirs, files in os.walk(exe_dir):
    for file in files:
        if file.endswith('.json') and 'model_prices' in file.lower():
            file_path = os.path.join(root, file)
            try:
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            except Exception:
                pass