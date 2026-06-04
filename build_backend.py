import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    import litellm
    litellm_dir = Path(litellm.__file__).parent
    
    print("Building backend...")
    
    subprocess.run([
        'pyinstaller',
        'backend.spec',
        '--distpath', 'frontend/backend',
        '--clean'
    ], check=True)
    
    backend_dist = Path('frontend/backend/desktopclaw')
    
    print(f"Copying litellm resources to {backend_dist}")
    
    for item in litellm_dir.rglob('*.json'):
        relative_path = item.relative_to(litellm_dir)
        dest_path = backend_dist / 'litellm' / relative_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(item, dest_path)
        print(f"Copied: {item} -> {dest_path}")
    
    print("Backend build complete!")

if __name__ == '__main__':
    main()
