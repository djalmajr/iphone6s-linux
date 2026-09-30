#!/usr/bin/env python3
"""Local visual countdown synchronized with palera1n's DFU prompt."""

import http.server
import json
import os
import pty
import re
import secrets
import signal
import subprocess
import threading
import time
from pathlib import Path
from dfu_state import finish_output, process_output

ROOT = Path(__file__).resolve().parent


def stop(_signal, _frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop)
TOKEN = secrets.token_urlsafe(24)
LOCK = threading.Lock()
STATE = {"ready": False, "phase": "starting", "log": "", "cue_at": None}
MASTER, SLAVE = pty.openpty()
ENV = os.environ.copy()
ENV["PALERA1N_BYPASS_PASSCODE_CHECK"] = "1"
PROC = subprocess.Popen(
    [str(ROOT / "palera1n-macos-arm64"), "-lp", "-k", str(ROOT / "Pongo.bin")],
    cwd=ROOT,
    env=ENV,
    stdin=SLAVE,
    stdout=SLAVE,
    stderr=SLAVE,
    start_new_session=True,
)
os.close(SLAVE)


def read_output():
    while True:
        try:
            chunk = os.read(MASTER, 4096)
        except OSError:
            break
        if not chunk:
            break
        clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", chunk.decode(errors="replace"))
        with LOCK:
            process_output(STATE, clean)
    with LOCK:
        finish_output(STATE)


threading.Thread(target=read_output, daemon=True).start()

HTML = r"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DFU iPhone 6s</title>
<style>
body{margin:0;background:#101726;color:#fff;font:20px system-ui,sans-serif}
main{max-width:900px;margin:32px auto;padding:24px;text-align:center}
h1{font-size:34px}#clock{font-size:clamp(90px,20vw,220px);font-weight:800;line-height:1.1;margin:24px 0}
#action{font-size:clamp(26px,5vw,54px);font-weight:700;min-height:130px}
button{font-size:28px;padding:18px 36px;border:0;border-radius:14px;background:#53d69c;color:#10231a;cursor:pointer}
button:disabled{opacity:.45;cursor:default}#status{color:#bcd0e9}
.guide{font-size:17px;line-height:1.5;text-align:left;background:#202d43;padding:16px 24px;border-radius:12px}
#log{white-space:pre-wrap;text-align:left;font-size:12px;color:#91a5bd;max-height:100px;overflow:auto}
</style><main><h1>DFU do iPhone 6s</h1>
<p id="status">Preparando o iPhone…</p><div id="clock">—</div>
<div id="action">Aguarde até aparecer o desenho do cabo no iPhone.</div>
<button id="start" disabled>Iniciar contagem</button>
<div class="guide"><p>Coloque um dedo em <b>Power</b> e outro no botão redondo <b>Home</b>. Clique em Iniciar e posicione os dedos durante a contagem de 5 segundos.</p>
<p>Em <b>VAI</b>: segure Power + Home. Após 4 segundos: solte só Power e mantenha Home. Após mais 10 segundos: solte Home. A tela deve ficar preta.</p></div>
<pre id="log"></pre></main>
<script>
const token = '__TOKEN__';
const status = document.getElementById('status'), clock = document.getElementById('clock');
const action = document.getElementById('action'), start = document.getElementById('start');
const log = document.getElementById('log'); let cueAt = null, phase = '';
function tick(){
 if(cueAt===null)return;
 const d=(Date.now()-cueAt)/1000;
 if(d<0){clock.textContent=Math.ceil(-d);action.textContent='Posicione os dedos em Power e Home';document.body.style.background='#101726'}
 else if(d<4){clock.textContent=d<.8?'VAI':Math.ceil(4-d);action.textContent='SEGURE POWER + HOME';document.body.style.background='#174831'}
 else if(d<14){clock.textContent=Math.ceil(14-d);action.textContent='SOLTE POWER. CONTINUE SEGURANDO HOME';document.body.style.background='#59421b'}
 else{clock.textContent='FIM';action.textContent='SOLTE HOME. A tela deve ficar preta.';document.body.style.background='#101726';cueAt=null}
}
setInterval(tick,50);
async function poll(){
 try{const s=await (await fetch('/state')).json(); phase=s.phase;log.textContent=s.log.slice(-1000);
  if(cueAt===null){start.disabled=!s.ready;status.textContent=s.ready?'Pronto: desenho do cabo no iPhone? Clique em Iniciar.':
   s.phase==='pongo'?'PongoOS iniciado.':s.phase==='dfu'?'DFU detectado pelo Mac.':
   s.phase==='failed'?'Falha no boot USB. Tentativa encerrada; não repita a contagem.':
   s.phase==='exited'?'A ferramenta encerrou.':'Aguardando recuperação…';}
 }catch(e){status.textContent='Conexão local indisponível';start.disabled=true}
}
setInterval(poll,500);poll();
start.onclick=async()=>{start.disabled=true;const r=await fetch('/start',{method:'POST',headers:{'X-DFU-Token':token}});const s=await r.json();
 if(!r.ok){status.textContent=s.error;return;}cueAt=s.cue_at;status.textContent='Contagem iniciada';tick();};
</script></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = HTML.replace("__TOKEN__", TOKEN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/state":
            with LOCK:
                self.send_json(dict(STATE))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/start" or self.headers.get("X-DFU-Token") != TOKEN:
            self.send_error(403)
            return
        with LOCK:
            if not STATE["ready"] or PROC.poll() is not None:
                self.send_json({"error": "A ferramenta ainda não está pronta."}, 409)
                return
            STATE["ready"] = False
            STATE["phase"] = "scheduled"
            STATE["cue_at"] = (time.time() + 5) * 1000
            cue_at = STATE["cue_at"]
        # The visual VAI precedes Enter by 0.4 s, allowing reaction time.
        threading.Timer(5.4, lambda: os.write(MASTER, b"\n")).start()
        self.send_json({"cue_at": cue_at})


try:
    http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
finally:
    if PROC.poll() is None:
        os.killpg(PROC.pid, signal.SIGTERM)
    os.close(MASTER)
