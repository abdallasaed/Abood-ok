import os
import re
import time
import urllib.parse
import threading
import requests
import html as html_lib

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

app = FastAPI()

session = requests.Session()
extracted_urls_cache = {}

# ==========================================
# Keep Alive (اختياري، للتشغيل المحلي أو منع النوم)
# ==========================================
def keep_alive():
    while True:
        try:
            port = int(os.environ.get("PORT", 8000))
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        except Exception:
            pass
        time.sleep(300)

threading.Thread(target=keep_alive, daemon=True).start()

# ==========================================
# أدوات مساعدة
# ==========================================
def get_secure_host(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost")
    scheme = request.headers.get("x-forwarded-proto", "https")
    return f"{scheme}://{host}"

def extract_okru(video_id: str):
    now = time.time()
    if video_id in extracted_urls_cache:
        cached = extracted_urls_cache[video_id]
        # زيادة مدة الكاش إلى ساعة (3600 ثانية) بدلاً من 60 ثانية
        if now - cached["timestamp"] < 3600:
            return cached["url"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }

    urls_to_try = [
        f"https://ok.ru/videoembed/{video_id}",
        f"https://m.ok.ru/live/{video_id}",
        f"https://m.ok.ru/video/{video_id}",
    ]

    for url in urls_to_try:
        try:
            resp = session.get(url, headers=headers, timeout=8)
            print(f"[LOG] {url} | {resp.status_code}")
            if resp.status_code != 200:
                continue
            source = html_lib.unescape(resp.text).replace("\\/", "/")
            match = re.search(r'(https?://[^"\'\s>\{\}\[\]]+\.m3u8[^"\'\s>\{\}\[\]]*)', source)
            if match:
                final_url = match.group(1).split('"')[0].split("'")[0]
                print(f"[LOG] Found: {final_url}")
                extracted_urls_cache[video_id] = {"url": final_url, "timestamp": now}
                return final_url
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
    return None

# ==========================================
# واجهة HTML
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aboud TV - OK.ru Extractor</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; text-align: center; padding: 50px 20px; margin: 0; }
        .container { max-width: 600px; margin: auto; background: #1e1e1e; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-top: 4px solid #f39c12; }
        h1 { color: #f39c12; margin-top: 0; margin-bottom: 5px; }
        p { color: #aaaaaa; font-size: 14px; margin-bottom: 25px; }
        input[type="text"] { width: 90%; padding: 15px; border-radius: 8px; border: 1px solid #333; background: #2a2a2a; color: #fff; font-size: 16px; margin-bottom: 20px; text-align: left; direction: ltr; }
        button { background: #f39c12; color: #000; font-weight: bold; padding: 15px 30px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: 0.3s; width: 95%; }
        button:hover { background: #e67e22; transform: scale(1.02); }
        .result-box { margin-top: 30px; background: #2a2a2a; padding: 20px; border-radius: 8px; border: 1px dashed #f39c12; display: none; }
        .result-url { word-break: break-all; color: #00e676; font-size: 15px; font-weight: bold; margin: 15px 0; direction: ltr; text-align: left;}
        .copy-btn { background: #00e676; color: #000; width: 50%; padding: 10px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Aboud TV 🚀</h1>
        <p>نظام سحب الروابط لـ AppCreator24</p>
        <input type="text" id="okUrl" placeholder="https://ok.ru/video/14855632920086 أو /live/">
        <button onclick="generateLink()">استخراج الرابط</button>
        <div class="result-box" id="resultBox">
            <h3 style="color: #fff; margin-bottom: 10px;">✅ الرابط جاهز لـ App24</h3>
            <div class="result-url" id="finalUrl"></div>
            <button class="copy-btn" onclick="copyUrl()">نسخ الرابط</button>
        </div>
    </div>
    <script>
        function generateLink() {
            let input = document.getElementById('okUrl').value;
            let match = input.match(/(\\d{8,})/);
            if(match && match[1]) {
                let videoId = match[1];
                let host = window.location.origin;
                let finalM3u8 = host + "/live/" + videoId + ".m3u8";
                document.getElementById('finalUrl').innerText = finalM3u8;
                document.getElementById('resultBox').style.display = 'block';
            } else {
                alert('الرجاء إدخال رابط OK.ru صحيح!');
            }
        }
        function copyUrl() {
            let text = document.getElementById('finalUrl').innerText;
            navigator.clipboard.writeText(text);
            alert('تم نسخ الرابط بنجاح!');
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE

# ==========================================
# مسارات البث
# ==========================================

# 1. مسار HEAD للاستجابة الفورية لطلبات التحقق من المشغل
@app.head("/live/{video_id}.m3u8")
def head_m3u8(video_id: str):
    return Response(
        status_code=200,
        media_type="application/vnd.apple.mpegurl",
        headers={"Content-Length": "0"}
    )

# 2. مسار GET الرئيسي لملف m3u8
@app.get("/live/{video_id}.m3u8")
def master_m3u8(video_id: str, request: Request):
    m3u8_url = extract_okru(video_id)
    if not m3u8_url:
        return HTMLResponse(content="#EXTM3U\n# Video not found", status_code=404, media_type="application/vnd.apple.mpegurl")

    resp = session.get(m3u8_url)
    host = get_secure_host(request)

    lines = []
    for line in resp.text.splitlines():
        if line.startswith("#"):
            lines.append(line)
        elif line.strip():
            url = line.strip()
            if not url.startswith("http"):
                url = f"{m3u8_url.rsplit('/', 1)[0]}/{url}"
            encoded_url = urllib.parse.quote(url, safe="")
            lines.append(f"{host}/proxy/playlist.m3u8?url={encoded_url}")

    return HTMLResponse(content="\n".join(lines), media_type="application/vnd.apple.mpegurl")

@app.get("/proxy/playlist.m3u8")
def proxy_playlist(url: str, request: Request):
    resp = session.get(url)
    host = get_secure_host(request)

    lines = []
    for line in resp.text.splitlines():
        if line.startswith("#"):
            lines.append(line)
        elif line.strip():
            ts_url = line.strip()
            if not ts_url.startswith("http"):
                ts_url = f"{url.rsplit('/', 1)[0]}/{ts_url}"
            encoded_url = urllib.parse.quote(ts_url, safe="")
            lines.append(f"{host}/proxy/segment.ts?url={encoded_url}")

    return HTMLResponse(content="\n".join(lines), media_type="application/vnd.apple.mpegurl")

@app.get("/proxy/segment.ts")
def proxy_segment(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        req = session.get(url, headers=headers, stream=True, timeout=15)

        def iterfile():
            for chunk in req.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk

        resp_headers = {"Content-Type": req.headers.get("Content-Type", "video/MP2T")}
        if "Content-Length" in req.headers:
            resp_headers["Content-Length"] = req.headers["Content-Length"]

        return StreamingResponse(iterfile(), headers=resp_headers)
    except Exception as e:
        print(f"[ERROR] segment: {e}")
        return StreamingResponse(iter([b""]), status_code=500, media_type="video/MP2T")

# ==========================================
# التشغيل المحلي
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
