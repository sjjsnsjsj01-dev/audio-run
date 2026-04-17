import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

# ========= إعدادات =========
INPUT = "input.wav"

STAGES_DIR = "stages"
BACKUP_DIR = "backup"
PROGRESS_FILE = "progress.json"

SAVE_INTERVAL = 300
KEEP_STAGES = 3
KEEP_BACKUPS = 1

LOOPS = 65536
ATEMPO_COUNT = 16

# ✅ تم تعبئة الريبو الصحيح
REPO = "sjjsnsjsj01-dev/audio-run"

os.makedirs(STAGES_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# ========= أدوات =========
def run(cmd):
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def get_info(path):
    out = subprocess.run(
        ["ffprobe","-v","error","-print_format","json","-show_format","-show_streams",path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, check=True
    ).stdout
    return json.loads(out)

# ========= Git =========
def git_setup():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("⚠️ لا يوجد GITHUB_TOKEN")
        return

    try:
        if not os.path.exists(".git"):
            print("🔧 init git")
            run(["git","init"])
            run(["git","branch","-M","main"])
            run(["git","remote","add","origin",f"https://{token}@github.com/{REPO}.git"])

        run(["git","config","--global","user.email","railway@bot.com"])
        run(["git","config","--global","user.name","Railway Bot"])

        # ✅ أول commit إذا فاضي
        if not Path(".git/refs/heads/main").exists():
            Path("init.txt").write_text("init")
            run(["git","add","."])
            run(["git","commit","-m","init"])
            run(["git","push","-u","origin","main","--force"])

        print("✅ Git جاهز")

    except Exception as e:
        print(f"❌ خطأ git: {e}")

def git_push(stage):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return

    status = subprocess.run(
        ["git","status","--porcelain"],
        stdout=subprocess.PIPE, text=True
    )

    if not status.stdout.strip():
        return

    run(["git","add","."])

    run([
        "git","commit",
        "-m",f"stage {stage} - {datetime.now().isoformat()}"
    ])

    run(["git","push","origin","main","--force"])

# ========= Progress =========
def save_progress(stage, file):
    with open(PROGRESS_FILE + ".tmp","w") as f:
        json.dump({"stage":stage,"file":file},f)
    os.replace(PROGRESS_FILE + ".tmp", PROGRESS_FILE)

def load_progress():
    if Path(PROGRESS_FILE).exists():
        return json.load(open(PROGRESS_FILE))
    return {"stage":0,"file":None}

# ========= تنظيف =========
def cleanup_stages():
    files = sorted(Path(STAGES_DIR).glob("stage_*.wav"),
                   key=lambda x:int(x.stem.split("_")[1]))
    for f in files[:-KEEP_STAGES]:
        f.unlink(missing_ok=True)

def cleanup_backups():
    files = sorted(Path(BACKUP_DIR).glob("stage_*.wav"),
                   key=lambda x:int(x.stem.split("_")[1]))
    for f in files[:-KEEP_BACKUPS]:
        f.unlink(missing_ok=True)

# ========= المعالجة =========
def process_stage(input_file, output_file):

    meta = get_info(input_file)
    stream = next(s for s in meta["streams"] if s["codec_type"]=="audio")

    sr = int(stream["sample_rate"])
    duration = float(meta["format"]["duration"])
    samples = int(sr * duration)

    aloop = f"aloop=loop={LOOPS-1}:size={samples}:start=0"
    atempo = ",".join(["atempo=2"] * ATEMPO_COUNT)

    filter_chain = f"{aloop},{atempo}"

    run([
        "ffmpeg",
        "-y",
        "-loglevel","quiet",
        "-i",input_file,
        "-filter:a",filter_chain,
        "-ar",str(sr),
        "-ac","2",
        "-c:a","pcm_s16le",
        output_file
    ])

# ========= بدء =========
def find_start():
    progress = load_progress()

    if progress["file"] and Path(progress["file"]).exists():
        return progress["file"], progress["stage"]

    stages = sorted(Path(STAGES_DIR).glob("stage_*.wav"),
                    key=lambda x:int(x.stem.split("_")[1]))

    if stages:
        last = stages[-1]
        return str(last), int(last.stem.split("_")[1])

    return INPUT, 0

# ========= تشغيل =========
def main():

    git_setup()

    current_file, stage = find_start()
    print(f"🚀 بدء من {stage}")

    while True:
        stage += 1
        output = f"{STAGES_DIR}/stage_{stage}.wav"

        print(f"🎧 مرحلة {stage}")

        process_stage(current_file, output)

        current_file = output
        save_progress(stage, current_file)

        cleanup_stages()

        if stage % SAVE_INTERVAL == 0:

            backup_file = f"{BACKUP_DIR}/stage_{stage}.wav"

            run([
                "ffmpeg","-y",
                "-loglevel","quiet",
                "-i",current_file,
                "-c:a","pcm_s16le",
                backup_file
            ])

            cleanup_backups()

            git_push(stage)

            print(f"🚀 تم الرفع عند المرحلة {stage}")

if __name__ == "__main__":
    main()