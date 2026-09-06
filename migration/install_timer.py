#!/usr/bin/env python3
"""为已验收的本机安装产品后台同步定时器。"""
import os
from pathlib import Path
import plistlib
import subprocess
import sys

home=Path.home()
exe=home/'.local/bin/skillstow'; config=home/'.config/skillstow/config.toml'
assert exe.is_file() and config.is_file(), '先安装并验收 SkillStow'
if sys.platform=='darwin':
    label='com.hcid274.skillstow'
    p=home/'Library/LaunchAgents'/f'{label}.plist';p.parent.mkdir(parents=True,exist_ok=True)
    log=home/'.local/state/skillstow';log.mkdir(parents=True,exist_ok=True)
    data={'Label':label,'ProgramArguments':[str(exe),'--config',str(config),'sync','--background'],
          'StartInterval':60,'EnvironmentVariables':{'PATH':os.environ['PATH']},
          'StandardOutPath':str(log/'sync.log'),'StandardErrorPath':str(log/'sync-error.log')}
    if p.exists(): raise SystemExit('定时器已存在，请审核并更新已有配置')
    p.write_bytes(plistlib.dumps(data))
    subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(p)],check=True)
elif '--cron' in sys.argv:
    import shlex
    result=subprocess.run(['crontab','-l'],capture_output=True,text=True)
    if result.returncode not in (0,1): raise SystemExit(result.stderr)
    assert '# skillstow-sync' not in result.stdout, '已有定时任务'
    log=home/'.local/state/skillstow';log.mkdir(parents=True,exist_ok=True)
    command=' '.join(shlex.quote(str(x)) for x in [exe,'--config',config,'sync','--background'])
    line=f'* * * * * {command} >> {shlex.quote(str(log/"sync.log"))} 2>&1 # skillstow-sync\n'
    subprocess.run(['crontab','-'],input=result.stdout.rstrip()+'\n'+line,text=True,check=True)
else:
    d=home/'.config/systemd/user';d.mkdir(parents=True,exist_ok=True)
    service=d/'skillstow.service';timer=d/'skillstow.timer'
    if service.exists() or timer.exists(): raise SystemExit('定时器已存在，请审核并更新已有配置')
    service.write_text('[Unit]\nDescription=Personal Skills Git synchronization\n\n[Service]\nType=oneshot\nExecStart=%h/.local/bin/skillstow --config %h/.config/skillstow/config.toml sync --background\nSuccessExitStatus=1\n')
    timer.write_text('[Unit]\nDescription=Sync personal Skills every minute\n\n[Timer]\nOnBootSec=60\nOnUnitInactiveSec=60\nAccuracySec=1\n\n[Install]\nWantedBy=timers.target\n')
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','--now','skillstow.timer'],check=True)
print('Installed 60-second SkillStow timer')
