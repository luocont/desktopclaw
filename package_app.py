import os
import shutil
import subprocess
from pathlib import Path

def main():
    frontend_dir = Path('frontend')
    dist_dir = frontend_dir / 'dist'
    app_dir = frontend_dir / 'app'
    
    print("Creating app directory structure...")
    
    if app_dir.exists():
        shutil.rmtree(app_dir)
    
    app_dir.mkdir(parents=True)
    
    print("Copying Electron resources...")
    subprocess.run([
        'npx', 'electron', '--version'
    ], check=True, capture_output=True)
    
    import electron
    electron_path = Path(electron.__file__).parent.parent
    
    print(f"Electron path: {electron_path}")
    
    shutil.copytree(
        electron_path / 'dist',
        app_dir / 'electron',
        dirs_exist_ok=True
    )
    
    print("Copying frontend dist...")
    shutil.copytree(
        dist_dir,
        app_dir / 'resources' / 'app',
        dirs_exist_ok=True
    )
    
    print("Copying backend...")
    shutil.copytree(
        frontend_dir / 'backend' / 'desktopclaw',
        app_dir / 'backend',
        dirs_exist_ok=True
    )
    
    print("Creating desktopclaw.exe launcher...")
    with open(app_dir / 'desktopclaw.bat', 'w') as f:
        f.write('@echo off\n')
        f.write('cd /d "%~dp0"\n')
        f.write('start /B backend\\desktopclaw.exe\n')
        f.write('timeout /t 5 /nobreak >nul\n')
        f.write('electron\\electron.exe resources\\app\n')
    
    print("Creating shortcut...")
    import winshell
    from win32com.client import Dispatch
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(str(app_dir / 'desktopclaw.lnk'))
    shortcut.TargetPath = str(app_dir / 'desktopclaw.bat')
    shortcut.WorkingDirectory = str(app_dir)
    shortcut.save()
    
    print("App packaged successfully!")
    print(f"App location: {app_dir}")

if __name__ == '__main__':
    main()
