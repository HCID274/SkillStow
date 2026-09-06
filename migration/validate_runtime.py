#!/usr/bin/env python3
"""在发布前校验候选里所有设备的 runtime，不触碰运行状态。"""
from pathlib import Path
import subprocess
import sys

for device in sorted(Path('systems').iterdir()):
    script=device/'.runtime/skillctl.py'
    if not script.is_file(): raise SystemExit(f'设备缺少 runtime：{device}')
    result=subprocess.run([sys.executable,'-B',str(script),'validate'],capture_output=True,text=True)
    if result.returncode:
        sys.stderr.write(result.stdout+result.stderr)
        raise SystemExit(result.returncode)
print('All device runtimes validated')
