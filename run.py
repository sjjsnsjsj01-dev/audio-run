#!/usr/bin/env python3

import os
import subprocess
import signal
import sys
import shutil
from datetime import datetime

# ================= 📦 CONFIG =================

# 🔥 طباعة تقرير
REPORT_EVERY = 1000

# 🔥 رفع GitHub
PUSH_EVERY = 10000

# 🔥 حفظ backup
BACKUP_EVERY = 50000

# 🔥 عدد مرات تطبيق الفلتر
FILTER_REPEAT = 35000

# 🔥 ffmpeg المعدل
FFMPEG_BIN = "./tiny/ffmpeg"

# 🔥 filter.txt
FILTER_FILE = "./filter.txt"

# 🔥 GitHub repo
REPO = "sjjsnsjsj01-dev/audio-run"

# 🔥 temp
SHM = "/dev/shm" if os.path.exists("/dev/shm") else "/tmp"

CURRENT = f"{SHM}/current.wav"
TMP = f"{SHM}/tmp.wav"

# ================= 🪵 LOG =================

def log(msg, level="INFO"):

    ts = datetime.now().strftime("%H:%M:%S")

    print(
        f"[{ts}] [{level}] {msg}",
        flush=True
    )

# ================= 🛡️ SIGNAL =================

shutdown_requested = False

def handle_signal(signum, frame):

    global shutdown_requested

    shutdown_requested = True

    log("⚠️ Shutdown requested", "WARN")

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# ================= 🌐 GIT =================

def git_setup():

    token = os.environ.get("GITHUB_TOKEN")

    if not token:

        log("⚠️ No GITHUB_TOKEN", "WARN")

        return False

    try:

        if not os.path.exists(".git"):

            subprocess.run(
                ["git", "init"],
                check=True
            )

            subprocess.run(
                ["git", "branch", "-M", "main"],
                check=True
            )

        subprocess.run(
            ["git", "remote", "remove", "origin"],
            stderr=subprocess.DEVNULL
        )

        subprocess.run([
            "git",
            "remote",
            "add",
            "origin",
            f"https://{token}@github.com/{REPO}.git"
        ], check=True)

        subprocess.run([
            "git",
            "config",
            "user.email",
            "bot@railway"
        ], check=True)

        subprocess.run([
            "git",
            "config",
            "user.name",
            "AudioBot"
        ], check=True)

        log("✅ GIT READY")

        return True

    except Exception as e:

        log(f"Git setup error: {e}", "ERROR")

        return False

# ================= ⬆️ PUSH =================

def git_push(stage):

    try:

        subprocess.run(
            ["git", "add", "."],
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            ["git", "commit", "-m", f"stage {stage}"],
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            ["git", "push", "origin", "main", "--force"],
            stderr=subprocess.DEVNULL
        )

        log(f"✅ PUSHED STAGE {stage}")

    except Exception as e:

        log(f"❌ PUSH FAILED: {e}", "ERROR")

# ================= 💾 BACKUP =================

def git_backup(stage, file_path):

    try:

        backup_dir = "backup"

        os.makedirs(
            backup_dir,
            exist_ok=True
        )

        backup_file = f"{backup_dir}/out{stage}.wav"

        shutil.copy2(
            file_path,
            backup_file
        )

        subprocess.run(
            ["git", "add", backup_file],
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            ["git", "commit", "-m", f"backup {stage}"],
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            ["git", "push", "origin", "main", "--force"],
            stderr=subprocess.DEVNULL
        )

        log(f"💾 BACKUP SAVED {backup_file}")

    except Exception as e:

        log(f"❌ BACKUP FAILED: {e}", "ERROR")

# ================= 🎬 FFMPEG =================

def ffmpeg_speed(inp, out):

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-loglevel", "quiet",
        "-i", inp
    ]

    # 🔥 تكرار الفلتر
    for _ in range(FILTER_REPEAT):

        cmd += [
            "-filter_script:a",
            FILTER_FILE
        ]

    cmd += [
        "-c:a",
        "pcm_s16le",
        out
    ]

    result = subprocess.run(cmd)

    return result.returncode == 0

# ================= 🚀 PROCESS =================

def process_stage(stage, input_file):

    if stage == 1:

        log(f"🚀 مرحلة {stage} بدأت")

        log(f"📥 input: {input_file}")

        log("⚡ بدء التسريع")

    shutil.copy2(
        input_file,
        CURRENT
    )

    ok = ffmpeg_speed(
        CURRENT,
        TMP
    )

    if not ok:

        log("❌ ffmpeg failed", "ERROR")

        return None

    if not os.path.exists(TMP):

        log("❌ TMP OUTPUT MISSING", "ERROR")

        return None

    if os.path.getsize(TMP) == 0:

        log("❌ TMP OUTPUT EMPTY", "ERROR")

        return None

    os.replace(
        TMP,
        CURRENT
    )

    out_file = f"out{stage}.wav"

    shutil.copy2(
        CURRENT,
        out_file
    )

    return os.path.abspath(out_file)

# ================= 🎮 MAIN =================

def main():

    log("🔥 ENGINE START")

    if not os.path.exists(FFMPEG_BIN):

        log("❌ CUSTOM FFMPEG NOT FOUND", "ERROR")

        sys.exit(1)

    if not os.path.exists(FILTER_FILE):

        log("❌ filter.txt missing", "ERROR")

        sys.exit(1)

    if not os.path.exists("input.wav"):

        log("❌ input.wav missing", "ERROR")

        sys.exit(1)

    os.chmod(
        FFMPEG_BIN,
        0o755
    )

    git_setup()

    log(f"🔥 FILTER_REPEAT = {FILTER_REPEAT}")

    current_input = os.path.abspath("input.wav")

    stage = 0

    while True:

        if shutdown_requested:

            sys.exit(0)

        stage += 1

        out_file = process_stage(
            stage,
            current_input
        )

        if not out_file:

            log("❌ فشل", "ERROR")

            sys.exit(1)

        # ================= 🗑️ DELETE OLD =================

        if stage == 1:

            if os.path.exists("input.wav"):

                os.remove("input.wav")

        else:

            prev = f"out{stage-1}.wav"

            if os.path.exists(prev):

                os.remove(prev)

        current_input = out_file

        # ================= 📊 REPORT =================

        if stage % REPORT_EVERY == 0:

            log(f"📊 تم إنجاز {stage} مرحلة")

        # ================= ⬆️ PUSH =================

        if stage % PUSH_EVERY == 0:

            git_push(stage)

        # ================= 💾 BACKUP =================

        if stage % BACKUP_EVERY == 0:

            git_backup(
                stage,
                current_input
            )

# ================= ENTRY =================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        sys.exit(130)

    except Exception as e:

        log(f"💥 {e}", "ERROR")

        import traceback

        traceback.print_exc()

        sys.exit(1)
