#!/usr/bin/env python3
"""为已验收的本机安装产品后台同步定时器。"""
import os
import base64
import json
from pathlib import Path
import plistlib
import subprocess
import sys

home=Path.home()
exe=home/'.local/bin'/('skillstow.exe' if os.name=='nt' else 'skillstow'); config=home/'.config/skillstow/config.toml'
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
elif os.name=='nt':
    # S4U 后台身份不依赖交互桌面，Git 使用本机仓库专用 SSH 密钥。
    payload=base64.b64encode(json.dumps({'exe':str(exe),'config':str(config)}).encode()).decode()
    command=r'''$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$d=[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('PAYLOAD')) | ConvertFrom-Json
$arguments='--config "'+$d.config+'" sync --background'
$existing=Get-ScheduledTask -TaskName SkillStowSync -ErrorAction SilentlyContinue
if ($existing) {
 if ($existing.Actions.Execute -eq $d.exe -and $existing.Actions.Arguments -eq $arguments) { exit 0 }
 throw 'Existing SkillStowSync has a different action; inspect before replacement.'
}
$action=New-ScheduledTaskAction -Execute $d.exe -Argument $arguments -WorkingDirectory $env:USERPROFILE
$trigger=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal=New-ScheduledTaskPrincipal -UserId ($env:COMPUTERNAME+'\'+$env:USERNAME) -LogonType S4U -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName SkillStowSync -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
'''.replace('PAYLOAD',payload)
    encoded=base64.b64encode(command.encode('utf-16le')).decode()
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],check=True)
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
