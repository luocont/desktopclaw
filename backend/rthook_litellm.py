import sys
import os
import shutil

def _setup_litellm_config():
    import pathlib
    
    temp_dir = pathlib.Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else pathlib.Path('.')
    
    litellm_dir = temp_dir / 'litellm'
    config_path = litellm_dir / 'model_prices_and_context_window_backup.json'
    
    if not litellm_dir.exists():
        litellm_dir.mkdir(parents=True, exist_ok=True)
    
    source_path = temp_dir / 'desktopclaw' / 'model_prices_and_context_window_backup.json'
    if source_path.exists() and not config_path.exists():
        shutil.copy(str(source_path), str(config_path))

_setup_litellm_config()
