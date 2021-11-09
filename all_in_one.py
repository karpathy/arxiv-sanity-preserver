import os
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
    if pre_proc is not None:
        print("preparing to restart downloading...")
        pre_proc.stdin.write('restart\n'.encode())
        pre_proc.stdin.flush()
        return pre_proc
    else:
        return subprocess.Popen("python download_pdfs.py", stdin=subprocess.PIPE)


if __name__ == '__main__':
    download_proc, next_day_float, first_start = None, time.time() + 24 * 3600, True

    if not os.path.exists(Config.db_path):
        sync_execs()
    download_proc = download_pdfs(None)

    while True:
        cur_hour = to_struct_time(time.localtime()).tm_hour
        if cur_hour == 12 and time.time() > next_day_float:  # update data and restart download at 12:00
            sync_execs()
            download_proc = download_pdfs(download_proc)
        subprocess.Popen("python thumb_pdf.py", creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(60 * 60)  # sync every 1 hour
