#!/usr/bin/env python3
"""Capture the README screenshots (docs/screenshots/) from the local dev stack.

    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    docker compose exec backend python manage.py seed_demo_data --reset
    pip install websocket-client pillow
    python3 scripts/screenshots.py [docs/screenshots]

Needs Google Chrome on the PATH (`google-chrome`). Portals on :4300 (Jenga) and :4200 (Fundi).
"""
import json, subprocess, time, urllib.request, tempfile, shutil, base64, sys, websocket
OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots"
def session(port, user, pw, pages, w=1440, h=900, pre=None, mobile=False):
    prof=tempfile.mkdtemp(); dbg=9800+port%100+(50 if mobile else 0)
    c=subprocess.Popen(["google-chrome","--headless=new","--no-sandbox","--hide-scrollbars",f"--remote-debugging-port={dbg}",f"--user-data-dir={prof}",f"--window-size={w},{h}","about:blank"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(50):
        try: tabs=json.load(urllib.request.urlopen(f"http://127.0.0.1:{dbg}/json")); break
        except Exception: time.sleep(0.2)
    ws=websocket.create_connection(next(t for t in tabs if t["type"]=="page")["webSocketDebuggerUrl"],suppress_origin=True); n=[0]
    def call(m,p={}):
        n[0]+=1; ws.send(json.dumps({"id":n[0],"method":m,"params":p}))
        while True:
            r=json.loads(ws.recv())
            if r.get("id")==n[0]: return r.get("result",{})
    ev=lambda js: call("Runtime.evaluate",{"expression":js,"returnByValue":True,"awaitPromise":True}).get("result",{}).get("value")
    if mobile:
        call("Emulation.setDeviceMetricsOverride",{"width":w,"height":h,"deviceScaleFactor":2,"mobile":True})
    call("Page.navigate",{"url":f"http://localhost:{port}/login"}); time.sleep(6)
    if pre: ev(pre); call("Page.navigate",{"url":f"http://localhost:{port}/login"}); time.sleep(5)
    shot=lambda name: (open(f"{OUT}/{name}.png","wb").write(base64.b64decode(call("Page.captureScreenshot",{})["data"])), print(name, ev("location.pathname")))
    if pages and pages[0][0].endswith("login"):
        shot(pages[0][0]); pages=pages[1:]
    fill=lambda sel,v: f"(()=>{{const e=document.querySelector('{sel}');e.value={json.dumps(v)};e.dispatchEvent(new Event('input',{{bubbles:true}}));}})()"
    ev(fill('#username',user)); ev(fill('#password',pw)); ev("document.querySelector('button[type=submit]').click()"); time.sleep(6)
    for name, route, js in pages:
        ev("document.body.click(); document.querySelectorAll('dialog[open]').forEach(d=>d.close()); window.scrollTo(0,0)")
        if route:
            ev(f"(()=>{{const a=[...document.querySelectorAll('a')].find(a=>a.getAttribute('href')==={json.dumps(route)}); if(a) a.click(); return !!a}})()")
            time.sleep(3.5)
        if js: ev(js); time.sleep(2.5)
        shot(name)
    ws.close(); c.terminate(); shutil.rmtree(prof,ignore_errors=True)

click = lambda text: f"(()=>{{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.includes({json.dumps(text)})); if(b) b.click(); return !!b}})()"
LIGHT = "localStorage.setItem('theme','light'); localStorage.setItem('lang','en')"
session(4300, "jenga-pro", "JengaPro2026!", [
  ("jenga-login", None, None),
  ("jenga-dashboard", None, None),
  ("jenga-notifications", None, "document.querySelector('.bell').click(); setTimeout(()=>document.querySelector('.notes').scrollTop=600, 400)"),
  ("jenga-verify-gigs", "/main-menu/verify-gigs", None),
  ("jenga-reject-gig", None, click("Reject")),
  ("jenga-workers-find", "/main-menu/manage-workers", click("Find by trade") + ";setTimeout(()=>document.querySelector('form.find button[type=submit]').click(),300)"),
  ("jenga-job-applicants", "/main-menu/job-posts", "[...document.querySelectorAll('.tbl tbody tr button.btn.sm')].find(b=>b.textContent.includes('new'))?.click()"),
  ("jenga-payroll", "/main-menu/workforce", click("30 days")),
  ("jenga-budgets", None, click("Budgets")),
  ("jenga-site-ratings", None, click("Site ratings")),
  ("jenga-safety", "/main-menu/safety", None),
  ("jenga-activity", "/main-menu/activity", None),
], pre=LIGHT)
session(4200, "fundi-pro", "FundiPro2026!", [
  ("fundi-login", None, None),
  ("fundi-dashboard", None, None),
  ("fundi-find-work", "/main-menu/search-gigs", click("Job alerts")),
  ("fundi-my-gigs", "/main-menu/gig-summary", click("Completed")),
  ("fundi-statement", None, click("Statement")),
  ("fundi-credit-score", "/main-menu/credit-score", None),
  ("fundi-profile", None, "document.querySelector('.user-btn').click(); setTimeout(()=>[...document.querySelectorAll('.menu a, .menu button')].find(e=>/profile/i.test(e.textContent))?.click(), 300); setTimeout(()=>document.querySelector('app-work-profile')?.scrollIntoView(), 3500)"),
], pre=LIGHT)
session(4200, "fundi-pro", "FundiPro2026!", [("fundi-kiswahili", None, None)],
        pre="localStorage.setItem('theme','light'); localStorage.setItem('lang','sw')")
session(4300, "jenga-pro", "JengaPro2026!", [("jenga-dark", None, None)],
        pre="localStorage.setItem('theme','dark'); localStorage.setItem('lang','en')")
session(4200, "fundi-pro", "FundiPro2026!", [("fundi-mobile", None, None)], w=390, h=844, mobile=True, pre=LIGHT)


# Shrink: halve 2x captures, 256-colour palette PNGs (~60 KB each).
import glob
from PIL import Image
for f in glob.glob(f"{OUT}/*.png"):
    im = Image.open(f).convert("RGB")
    if "mobile" in f:
        im = im.resize((im.width * 3 // 4, im.height * 3 // 4), Image.LANCZOS)
    im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, optimize=True)
