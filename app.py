"""Kovetz maker: a small local website. Run:  python app.py   then open http://127.0.0.1:5000"""
import os, json, uuid, threading, datetime, traceback
from flask import Flask, Response, jsonify, request, render_template, send_file, abort

from kovetz import pipeline, render, booklet, dvar as dvar_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
SETTINGS_FILE = os.path.join(ROOT, "data", "settings.json")
os.makedirs(OUT, exist_ok=True)

app = Flask(__name__)


@app.before_request
def password_gate():
    """When SITE_PASSWORD is set (online hosting), every page asks for it. The username can be anything."""
    pw = os.environ.get("SITE_PASSWORD")
    if not pw:
        return None
    a = request.authorization
    if a and a.password == pw:
        return None
    return Response("Password needed", 401, {"WWW-Authenticate": 'Basic realm="Kovetz"'})


def prune_old(hours=24):
    import shutil, time
    for n in os.listdir(OUT):
        p = os.path.join(OUT, n)
        if os.path.isdir(p) and time.time() - os.path.getmtime(p) > hours * 3600:
            shutil.rmtree(p, ignore_errors=True)


JOBS = {}                                  # job id -> dict
LOCK = threading.Lock()


def load_settings():
    s = dict(pipeline.DEFAULT_SETTINGS)
    try:
        s.update(json.load(open(SETTINGS_FILE, encoding="utf-8")))
    except Exception:
        pass
    return s


def save_settings(s):
    keep = {k: s[k] for k in ("location", "location_label", "byline") if k in s}
    cur = load_settings()
    cur.update(keep)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
    return cur


def next_friday(today=None):
    t = today or datetime.date.today()
    return t + datetime.timedelta(days=(4 - t.weekday()) % 7)


def new_job():
    prune_old()
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "status": "running", "progress": [], "error": None, "issue": None, "files": {}}
    with LOCK:
        JOBS[jid] = job
    return job


def run_fetch(job, d, settings):
    try:
        issue = pipeline.build_issue(d, settings, progress=lambda m: job["progress"].append(m))
        job["issue"] = issue
        job["status"] = "fetched"
    except Exception as e:
        traceback.print_exc()
        job["error"] = str(e) or type(e).__name__
        job["status"] = "error"


def run_build(job):
    try:
        issue = job["issue"]
        d = issue["date"]
        folder = os.path.join(OUT, job["id"])
        os.makedirs(folder, exist_ok=True)
        std = os.path.join(folder, f"Kovetz-Erev-Shabbos_{d}_reading.pdf")
        bk = os.path.join(folder, f"Kovetz-Erev-Shabbos_{d}_booklet-print.pdf")
        job["progress"].append("Laying out the pages")
        pages = render.render_standard(issue, std, os.path.join(folder, "work"))
        job["progress"].append("Arranging the booklet for printing")
        n, pad = booklet.impose(std, bk)
        job["files"] = {"reading": std, "booklet": bk}
        job["stats"] = {"pages": n - pad, "sheets": n // 4, "blank": pad, "contents": pages}
        job["status"] = "built"
    except Exception as e:
        traceback.print_exc()
        job["error"] = str(e) or type(e).__name__
        job["status"] = "error"


def public(job):
    out = {"id": job["id"], "status": job["status"], "progress": job["progress"], "error": job["error"],
           "stats": job.get("stats")}
    iss = job.get("issue")
    if iss and job["status"] in ("fetched", "built"):
        m = iss["meta"]
        out["summary"] = {
            "parsha": f"{m['parsha_en']} · {m['parsha_he']}", "hebrew_date": m["hebrew_date_he"], "greg": m["greg_en"],
            "chumash": m["chumash_range_he"], "candle": f"{iss['candle']['time']} (for {iss['candle']['greg_en']})",
            "place": iss["candle"].get("place") or iss["candle"]["location_he"],
            "rambam": ", ".join(c["title"] for c in iss["rambam"]),
            "tanya": " / ".join(x for x in (iss["tanya"]["section_en"], iss["tanya"]["heading_en"]) if x) or "Tanya",
            "shnayim": f"{sum(len(c['verses']) for c in iss['shnayim'])} pesukim"}
        out["warnings"] = iss["warnings"]
        out["dvar"] = iss["dvar"]
    return out


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/defaults")
def defaults():
    s = load_settings()
    return jsonify({"date": next_friday().isoformat(), "settings": {k: s[k] for k in ("location", "location_label", "byline")},
                    "has_key": bool(os.environ.get("ANTHROPIC_API_KEY"))})


@app.post("/api/fetch")
def fetch():
    body = request.get_json(force=True)
    try:
        d = datetime.date.fromisoformat(body["date"])
    except Exception:
        return jsonify({"error": "Enter a valid date."}), 400
    settings = save_settings(body.get("settings", {}))
    job = new_job()
    threading.Thread(target=run_fetch, args=(job, d, settings), daemon=True).start()
    return jsonify({"id": job["id"]})


@app.get("/api/job/<jid>")
def job_status(jid):
    job = JOBS.get(jid) or abort(404)
    return jsonify(public(job))


@app.post("/api/dvar/<jid>")
def regen_dvar(jid):
    job = JOBS.get(jid) or abort(404)
    iss = job["issue"] or abort(400)
    m = iss["meta"]
    en, yi, note = dvar_mod.generate(m["parsha_en"], m["parsha_he"], m["chumash_range_he"])
    iss["dvar"] = {"english": en, "yiddish": yi, "note": note}
    return jsonify(iss["dvar"])


@app.post("/api/build/<jid>")
def build(jid):
    job = JOBS.get(jid) or abort(404)
    if not job.get("issue"):
        abort(400)
    body = request.get_json(force=True)
    d = body.get("dvar") or {}
    job["issue"]["dvar"].update({"english": d.get("english", ""), "yiddish": d.get("yiddish", "")})
    if "settings" in body:
        s = save_settings(body["settings"])
        job["issue"]["settings"].update({k: s[k] for k in ("location_label", "byline")})
        job["issue"]["candle"]["location_he"] = s["location_label"]
    job["status"] = "building"
    job["error"] = None
    threading.Thread(target=run_build, args=(job,), daemon=True).start()
    return jsonify({"id": job["id"]})


@app.get("/download/<jid>/<kind>")
def download(jid, kind):
    job = JOBS.get(jid) or abort(404)
    p = job.get("files", {}).get(kind) or abort(404)
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
