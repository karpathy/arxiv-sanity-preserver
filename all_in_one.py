import os
import signal
import subprocess
import time

from utils import to_struct_time, Config

if __name__ == '__main__':
    fetcher = "python fetch_papers.py\n"
    sim = "python analyze.py\n"
    user_sim = "python buildsvm.py\n"
    cache = "python make_cache.py\n"
    downloader = "python download_pdfs.py"
    thumbnail = "python thumb_pdf.py"
    tmp_script_file = "tmp_script.py"

    download_process = None
    if os.path.exists(Config.db_path):
        download_process = subprocess.Popen(downloader, shell=True)

    while True:
        if to_struct_time(time.localtime()).tm_hour == 12:  # exec async tmp file every day at 12:00
            tmp_script = open(tmp_script_file, "a")
            tmp_script.writelines([fetcher, sim, user_sim, cache])
            tmp_script.close()
            time.sleep(30)  # waiting 30 seconds of create file
            subprocess.Popen("python " + tmp_script_file, creationflags=subprocess.CREATE_NEW_CONSOLE)
        if to_struct_time(time.localtime()).tm_hour == 14:  # restart download at 14:00
            if os.path.exists(tmp_script_file):
                os.remove(tmp_script_file)
            if downloader is not None:
                download_process.send_signal(signal.CTRL_C_EVENT)
                time.sleep(30)  # waiting 30 seconds of terminate time
            if os.path.exists(Config.db_path):
                download_process = subprocess.Popen(fetcher, shell=True)
        subprocess.Popen(thumbnail, creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(45 * 60)  # sync every 40 minutes
