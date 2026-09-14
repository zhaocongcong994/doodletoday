#!/usr/bin/env python3
"""Install independent local dependencies. Never reuse credentials from other projects."""
from pathlib import Path
import os
import secrets
import shutil
import subprocess
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
os.chdir(root)
if sys.version_info<(3,10):
    alternate=shutil.which('python3.10') or shutil.which('python3.11') or shutil.which('python3.12')
    if alternate: os.execv(alternate,[alternate,__file__,*sys.argv[1:]])
    raise SystemExit('需要 Python 3.10+，请安装后重新运行。')
venv=root/'.venv'
if not venv.exists(): subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
subprocess.run([str(venv/'bin/python'),'-m','pip','install','-r','requirements.txt'],check=True)
if '--ocr' in sys.argv: subprocess.run([str(venv/'bin/python'),'-m','pip','install','-r','requirements-ocr.txt'],check=True)
subprocess.run(['npm','ci' if (root/'package-lock.json').exists() else 'install'],check=True)
font=root/'renderer/fonts/NotoSansSC-Regular.ttf'
if not font.exists():
    subprocess.run([str(venv/'bin/python'),'-m','pip','install','fonttools==4.59.1'],check=True)
    source=root/'renderer/fonts/NotoSansSC-VF.ttf'
    urllib.request.urlretrieve('https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/Variable/TTF/Subset/NotoSansSC-VF.ttf',source)
    subprocess.run([str(venv/'bin/python'),'-c',"from fontTools.ttLib import TTFont; from fontTools.varLib.instancer import instantiateVariableFont; instantiateVariableFont(TTFont('renderer/fonts/NotoSansSC-VF.ttf'),{'wght':400},inplace=True).save('renderer/fonts/NotoSansSC-Regular.ttf')"],check=True)
    source.unlink()
    urllib.request.urlretrieve('https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE',root/'renderer/fonts/OFL.txt')
if not (root/'.env').exists():
    text=(root/'.env.example').read_text().replace('INVITE_CODE=','INVITE_CODE='+secrets.token_urlsafe(12),1).replace('RENDER_TOKEN=','RENDER_TOKEN='+secrets.token_urlsafe(32),1)
    (root/'.env').write_text(text)
    os.chmod(root/'.env',0o600)
subprocess.run(['npm','run','build'],check=True)
print('初始化完成。邀请口令已写入本项目 .env；模型配置保持空白。运行 npm start。')
