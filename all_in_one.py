import os
import signal
import subprocess
import time
import fetch_papers, analyze, buildsvm, make_cache

from utils import to_struct_time, Config


def sync_execs():
    fetch_papers.run()
    analyze.run()
    buildsvm.run()
    make_cache.run()


def download_pdfs(pre_proc):
    if pre_proc is not None and pre_proc.poll() is not None:
        pre_proc.send_signal(signal.CTRL_C_EVENT)
        time.sleep(30)  # waiting 30 seconds of terminate time
    return subprocess.Popen(downloader, shell=True)


if __name__ == '__main__':
    downloader = "python download_pdfs.py"
    thumbnail = "python thumb_pdf.py"

    download_proc, next_day_float, first_start = None, time.time() + 24 * 3600, True

    if not os.path.exists(Config.db_path):
        sync_execs()
    download_proc = download_pdfs(None)

    while True:
        cur_hour = to_struct_time(time.localtime()).tm_hour
        if cur_hour == 12 and time.time() > next_day_float:
            sync_execs()
        if cur_hour == 14 and time.time() > next_day_float:  # restart download at 14:00
            download_proc = download_pdfs(download_proc)
        subprocess.Popen(thumbnail, creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(60 * 60)  # sync every 1 hour
