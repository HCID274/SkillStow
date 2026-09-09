"""只启动客户端控制协议并读取 Skill 清单，不发送模型任务。"""
import argparse
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('client', choices=['codex', 'claude'])
p.add_argument('executable')
p.add_argument('--cwd', default=str(Path.home()))
a = p.parse_args()
args = [a.executable, 'app-server'] if a.client == 'codex' else [a.executable, '--print', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose']
process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           text=True, encoding='utf-8', start_new_session=os.name != 'nt', cwd=a.cwd)
messages = queue.Queue()


def reader():
    for line in process.stdout:
        try:
            messages.put(json.loads(line))
        except json.JSONDecodeError:
            pass


threading.Thread(target=reader, daemon=True).start()


def send(value):
    process.stdin.write(json.dumps(value) + '\n'); process.stdin.flush()


try:
    if a.client == 'codex':
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'skillstow-verification', 'version': '0.2.0'}}})
    else:
        send({'type': 'control_request', 'request_id': 'init', 'request': {'subtype': 'initialize'}})
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        value = messages.get(timeout=max(0.1, deadline - time.monotonic()))
        if a.client == 'codex' and value.get('id') == 1:
            if 'error' in value: raise RuntimeError(value['error'])
            send({'method': 'initialized', 'params': {}})
            send({'id': 2, 'method': 'skills/list', 'params': {'cwds': [a.cwd], 'forceReload': True}})
        elif a.client == 'codex' and value.get('id') == 2:
            if 'error' in value: raise RuntimeError(value['error'])
            print(json.dumps(value['result'], ensure_ascii=False)); break
        elif a.client == 'claude' and value.get('type') == 'control_response':
            print(json.dumps(value, ensure_ascii=False)); break
    else:
        raise TimeoutError('客户端未返回清单')
finally:
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
    process.wait(timeout=5)
