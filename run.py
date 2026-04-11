import os
import json
import subprocess
import time
import sys
import shutil
import signal
import itertools
from pathlib import Path
from datetime import datetime, timedelta

# ================= Configuration =================
REPO = "sjjsnsjsj01-dev/audio-run"
STAGES_DIR = "stages"
BACKUP_DIR = "backup"
PROGRESS_FILE = "progress.json"

# 🚀 الإعدادات المطلوبة للمليار
ITERATIONS_PER_STAGE = 1000000000   # دمج الملف مع نفسه مليار مرة
SPEED_FACTOR = 1000000000           # تسريع الناتج مليار مرة

# ⏱️ الحفظ الزمني (كل 10 دقائق)
SAVE_INTERVAL_MINUTES = 10          # حفظ كل 10 دقائق
FFMPEG_TIMEOUT = 3600               # مهلة ساعة للمعالجة

BACKUP_RETAIN = 50                  # الاحتفاظ بآخر 50 نسخة
CLEANUP_RETAIN = 3                  # الاحتفاظ بآخر 3 ملفات stages

for d in [STAGES_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

# ================= Logging System =================
def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)

def log_debug(msg):
    if os.environ.get("DEBUG"):
        log(msg, "DEBUG")

# ================= Signal Handling =================
shutdown_requested = False
def handle_signal(signum, frame):
    global shutdown_requested
    log("⚠️ تم استلام إشارة إيقاف، جاري الحفظ الآمن والخروج...", "WARN")
    shutdown_requested = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# ================= Git Setup =================
def git_setup():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        log("⚠️ لم يتم العثور على GITHUB_TOKEN، تخطي إعدادات الجيت", "WARN")
        return False
    try:
        if not os.path.exists(".git"):
            log("🔧 جاري تهيئة مستودع الجيت...")
            subprocess.run(["git", "init"], check=True, capture_output=True)
            subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "origin", f"https://{token}@github.com/{REPO}.git"],
                check=True, capture_output=True
            )
        subprocess.run(["git", "config", "--global", "user.email", "railway@bot.com"], check=True, capture_output=True)
        subprocess.run(["git", "config", "--global", "user.name", "Railway Bot"], check=True, capture_output=True)
        log("✅ اكتمل إعداد الجيت")
        return True
    except Exception as e:
        log(f"❌ فشل إعداد الجيت: {e}", "ERROR")
        return False

# ================= Git Push =================
def git_push(stage, timeout=120):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        log("⚠️ لا يوجد GITHUB_TOKEN، تخطي الرفع", "WARN")
        return False
    try:
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=30)
        if not status.stdout.strip():
            log("📭 لا توجد تغييرات جديدة للرفع")
            return True
        log("📤 جاري الرفع إلى GitHub...")
        subprocess.run(["git", "add", "."], check=True, capture_output=True, timeout=30)
        subprocess.run(["git", "commit", "-m", f"stage {stage} - {datetime.now().isoformat()}"], check=True, capture_output=True, timeout=30)
        subprocess.run(["git", "push", "origin", "main", "--force"], check=True, capture_output=True, timeout=timeout)
        log(f"🚀 تم الرفع بنجاح للمرحلة {stage}")
        return True
    except subprocess.TimeoutExpired:
        log("❌ انتهت مهلة عملية الجيت", "ERROR")
        return False
    except Exception as e:
        log(f"❌ فشل رفع الجيت: {e}", "ERROR")
        return False

# ================= Progress =================
def save_progress(stage, file, atomic=True):
    data = {"stage": stage, "file": file, "timestamp": datetime.now().isoformat()}
    temp_file = f"{PROGRESS_FILE}.tmp"
    with open(temp_file, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_file, PROGRESS_FILE)
    log_debug(f"💾 تم حفظ التقدم: المرحلة {stage}")

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
            if "stage" in data and "file" in data:
                if os.path.exists(data["file"]):
                    return data["file"], data["stage"]
                log(f"⚠️ ملف التقدم موجود لكن الملف الهدف مفقود: {data['file']}", "WARN")
        except Exception as e:
            log(f"⚠️ فشل تحميل ملف التقدم: {e}", "WARN")
    return None, None

# ================= Resume Logic =================
def find_resume():
    file, stage = load_progress()
    if file and stage:
        log("=================================")
        log(f"✅ استئناف من المرحلة {stage}")
        log(f"📁 {file}")
        log("=================================")
        return file, stage
    
    backups = sorted(
        Path(BACKUP_DIR).glob("stage_*.wav"),
        key=lambda x: int(x.stem.split("_")[1]) if x.stem.split("_")[1].isdigit() else 0
    )
    if backups:
        last = backups[-1]
        stage = int(last.stem.split("_")[1])
        log("=================================")
        log(f"🔎 تم العثور على نسخة احتياطية في المرحلة {stage}")
        log(f"📁 {last}")
        log("=================================")
        return str(last), stage
    
    stages = sorted(
        Path(STAGES_DIR).glob("stage_*.wav"),
        key=lambda x: int(x.stem.split("_")[1]) if x.stem.split("_")[1].isdigit() else 0
    )
    if stages:
        last = stages[-1]
        stage = int(last.stem.split("_")[1])
        log("=================================")
        log(f"🔎 تم العثور على ملف مرحلة في المرحلة {stage}")
        log(f"📁 {last}")
        log("=================================")
        return str(last), stage
    
    raise Exception("❌ لم يتم العثور على ملف بداية - يرجى توفير ملف WAV أولي")

# ================= FFmpeg Processing =================
def get_audio_info(path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return json.loads(result.stdout)

def build_atempo_chain(speed):
    """بناء سلسلة atempo للسرعات الضخمة (حتى المليار وأكثر)"""
    parts = []
    remaining = float(speed)
    
    while remaining > 2.0:
        parts.append("2.0")
        remaining /= 2.0
    
    if remaining > 0.5:
        parts.append(f"{remaining:.10f}")
    
    return ",".join(f"atempo={p}" for p in parts)

def process_stage(input_file, output_file):
    try:
        meta = get_audio_info(input_file)
        stream = next(s for s in meta["streams"] if s["codec_type"] == "audio")
        sr = int(stream.get("sample_rate", 48000))
        ch = int(stream.get("channels", 2))
        
        # 🔢 حساب دقيق لعدد العينات من حجم الملف
        file_size = os.path.getsize(input_file)
        header_size = 44
        audio_bytes = max(0, file_size - header_size)
        bytes_per_sample = 2 * ch
        samples = audio_bytes // bytes_per_sample
        
        if samples == 0:
            raise ValueError("الملف فارغ أو غير صالح")
        
        # 🔄 دمج مليار مرة + تسريع مليار مرة
        aloop_filter = f"aloop=loop={ITERATIONS_PER_STAGE - 1}:size={samples}:start=0"
        atempo_chain = build_atempo_chain(SPEED_FACTOR)
        filter_complex = f"{aloop_filter},{atempo_chain}"
        
        log(f"📊 مرحلة | عينات: {samples:,} | تكرار: {ITERATIONS_PER_STAGE:,} | تسريع: {SPEED_FACTOR:,}x")
        
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-threads", "0", "-filter_threads", "0", "-filter_complex_threads", "0",
            "-i", input_file,
            "-filter:a", filter_complex,
            "-ar", str(sr), "-ac", str(ch),
            "-c:a", "pcm_s16le",
            "-max_muxing_queue_size", "9999",
            output_file
        ]
        
        subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT)
        
        if not os.path.exists(output_file) or os.path.getsize(output_file) < 44:
            raise Exception("الملف الناتج غير صالح أو فارغ")
            
        log_debug(f"✅ تمت المعالجة بنجاح: {os.path.basename(output_file)}")
        return True
        
    except subprocess.TimeoutExpired:
        log(f"❌ انتهت مهلة FFmpeg ({FFMPEG_TIMEOUT}s)", "ERROR")
        return False
    except Exception as e:
        log(f"❌ فشل المعالجة: {e}", "ERROR")
        return False

# ================= Cleanup & Backup =================
def cleanup_stages(keep_last=CLEANUP_RETAIN):
    try:
        files = sorted(
            Path(STAGES_DIR).glob("stage_*.wav"),
            key=lambda x: int(x.stem.split("_")[1]) if x.stem.split("_")[1].isdigit() else 0
        )
        for f in files[:-keep_last] if len(files) > keep_last else []:
            try: os.remove(f)
            except: pass
    except: pass

def create_backup(source_file, stage):
    backup_file = f"{BACKUP_DIR}/stage_{stage}.wav"
    try:
        shutil.copy2(source_file, backup_file)
        return backup_file
    except Exception as e:
        log(f"❌ فشل النسخ الاحتياطي: {e}", "ERROR")
        return None

def cleanup_backups(keep_last=BACKUP_RETAIN):
    try:
        files = sorted(
            Path(BACKUP_DIR).glob("stage_*.wav"),
            key=lambda x: int(x.stem.split("_")[1]) if x.stem.split("_")[1].isdigit() else 0
        )
        for f in files[:-keep_last] if len(files) > keep_last else []:
            try: os.remove(f)
            except: pass
    except: pass

# ================= Restart =================
def restart_script():
    log("♻️ جاري إعادة تشغيل run.py لتحرير الذاكرة...")
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ================= Main =================
def main():
    log("🎬 بدء تشغيل معالج التكرار الفائق (لا نهائي)...")
    log(f"🔁 كل مرحلة = {ITERATIONS_PER_STAGE:,} دمج + تسريع {SPEED_FACTOR:,}x")
    log(f"⏱️ الحفظ automático كل {SAVE_INTERVAL_MINUTES} دقائق")
    log(f"🎯 المدة النهائية ثابتة | النغمة محفوظة 100% | WAV فقط")
    
    git_setup()
    current_file, start_stage = find_resume()
    log(f"🚀 البدء من المرحلة {start_stage} (تشغيل لا نهائي)")
    
    # ⏱️ تتبع الوقت للحفظ الزمني
    last_save_time = datetime.now()
    save_interval = timedelta(minutes=SAVE_INTERVAL_MINUTES)
    
    # حلقة لا نهائية آمنة
    for stage in itertools.count(start_stage + 1):
        if shutdown_requested:
            log("🛑 تم طلب الإيقاف، جاري الحفظ والخروج الآمن...")
            save_progress(stage - 1, current_file)
            sys.exit(0)
        
        output_file = f"{STAGES_DIR}/stage_{stage}.wav"
        
        if stage % 100 == 0:
            log(f"📈 جاري المعالجة... المرحلة {stage:,}")
        
        success = process_stage(current_file, output_file)
        if not success:
            log(f"❌ فشل في المرحلة {stage}، إعادة المحاولة بعد انتظار...", "ERROR")
            time.sleep(5)
            if not process_stage(current_file, output_file):
                log(f"💥 فشل حرج في المرحلة {stage}", "ERROR")
                save_progress(stage - 1, current_file)
                sys.exit(1)
        
        current_file = output_file
        cleanup_stages()
        
        # ⏱️ التحقق مما إذا حان وقت الحفظ (كل 10 دقائق)
        current_time = datetime.now()
        if current_time - last_save_time >= save_interval:
            log(f"📦 وقت الحفظ الدوري (مر {SAVE_INTERVAL_MINUTES} دقائق) - المرحلة {stage:,}")
            
            backup_file = create_backup(current_file, stage)
            if not backup_file:
                log("⚠️ فشل النسخ الاحتياطي، المتابعة", "WARN")
                backup_file = current_file
                
            save_progress(stage, backup_file)
            cleanup_backups()
            git_push(stage)
            
            last_save_time = current_time
            restart_script()
    
    log("🎉 اكتملت العملية!")

# ================= Entry Point =================
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"💥 خطأ غير متوقع: {e}", "ERROR")
        sys.exit(1)
