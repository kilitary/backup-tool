import os
import random
import shutil
import sys
from os.path import join, getsize
import json
from pprint import pprint
import tempfile
from os import scandir
import configparser
from shutil import copytree
import time
import subprocess
import psutil
import atexit
import glob

config_file = "backup-tool.ini"
current_root = ''
config = configparser.ConfigParser()
done_dirs = []
dirs = []


def pred(text, send=''):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(255, 0, 0, text), end=send)


def pgray(text):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(11, 110, 0, text))


def pgreen(text, send=''):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(11, 110, 110, text), end=send)


def pblue(text):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(111, 210, 110, text))


def pblack(text, send='\n'):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(21, 25, 244, text), end=send)


def dump(data, exit=False):
    pprint(data)
    if exit:
        sys.exit()


def _logpath(path, m=None):
    print(f'processing {path} => {current_root}')


def load_config():
    config.read(config_file)
    print(f'{config.sections()}')


def erase_dir(erase_dir=None):
    if erase_dir == None:
        return
    print(f'erase {erase_dir} storage before')

    if len(erase_dir) == 3 or len(erase_dir) == 2:
        pred(f'could not erase root dir!')
        return

    shutil.rmtree(erase_dir, ignore_errors=True)

    print('erase complete')


def p_exit():
    not_done = [d for d in dirs if d not in done_dirs]
    print(f'done: {done_dirs} error: {not_done}')
    sys.exit(0)


def get_dir_setups():
    dirs = []
    for i, o in config["directories"].items():
        dirs.append((o, i))
    return dirs


def make_directories(dir):
    try:
        if not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)
    except IOError as e:
        print(f'exception while creating dir {dir}: {e.errno} {os.strerror(e.errno)}')


def get_root_dest():
    return config['settings']['dest']


def pack_files(dest_dir, src):
    temp_dst = os.path.join(tempfile.gettempdir(), 'backup-tool')
    make_directories(temp_dst)

    tmp_file = os.path.join(tempfile.gettempdir(), 'backup-tool', f'{time.time_ns()}.tmp')
    tmp_list = os.path.join(tempfile.gettempdir(), 'backup-tool', 'list.txt')
    final_archive = os.path.join(dest_dir, 'files.7z')
    files = [file.path + '\n' for file in os.scandir(src) if file.is_file()]

    if not len(files):
        return

    if os.path.exists(final_archive):
        print(f'skip {final_archive}')
        return

    with open(tmp_list, "wt") as f:
        f.writelines(files)

    print(f'packing {len(files)} files in {src} ... ', end='')
    p = subprocess.Popen(["7z", "a", "-t7z", "-bb0", "-y", "-mx1", f"-i@{tmp_list}", tmp_file])
    p.wait()
    print(f'moving ', end='')
    shutil.move(tmp_file, final_archive)

    print(f'done')


def process_directory(dir=None, current_dst='', current_src=""):
    """
    copy directory (recursive)
    """
    global current_root

    dir = current_src if dir is None else dir

    try:
        pack_files(current_dst, dir)

        dirs = os.scandir(dir)
    except Exception as e:
        print(f'scandir {e.errno}: {e}')

        if e.errno == 13:
            print(f'access denied')
            return

        p_exit()

    # print(f'{current_src} => {current_dst}')

    for entry in dirs:
        try:
            if not entry.is_dir() or entry.name in [".", ".."]:
                continue

            dest_dir = os.path.join(current_dst, entry.name)
            current_root = dest_dir

            assert dest_dir.count(get_root_dest()) != 0, f'error: nocopy to {dest_dir}'
            make_directories(dest_dir)
            src_dir = os.path.join(current_src, entry.name)
            src = os.path.join(dir, entry.name)
            process_directory(dir=src, current_dst=dest_dir, current_src=src_dir)

            pack_files(dest_dir, src)

            # sys.exit(0)

            # else:
            #     dest_dir = os.path.join(current_dst, dir[3:])
            #
            #     assert dest_dir.count(get_root_dest()) != 0, f'error: nocopy to {dest_dir}'
            #
            #     dest_file = os.path.join(current_dst, entry.name)
            #     # print(f'copy {entry.path} to {dest_file}')
            #     # copyfile(entry.path, dest_file)
        except Exception as e:
            print(f'exception while copying dir {dir}: {e.errno} {e.strerror}', e)

            if e.errno == 28:
                pred(f'storage exhaused')
                p_exit()
            if e.errno == 13:
                print(f'access denied')

            continue


def copyfile(src, dst, buf_siz=1024 * 1024 * 4):
    """
    Copy a file
    """

    assert os.path.isfile(src), f"copyfile: file {src} is dir"

    try:
        if os.path.exists(dst):
            os.unlink(dst)

        copy_total = os.path.getsize(src)
        copy_done = 0

        src_f = open(src, mode="rb")
        dst_f = open(dst, mode='xb')

        print(f'copying {copy_total / 1024.0 / 1024.0:.2f}Mb {src} to {dst} ... ', end='', file=sys.stdout, flush=True)

        while True:
            copy_buffer = src_f.read(buf_siz)
            if not copy_buffer:
                break
            copy_done += dst_f.write(copy_buffer)
            t = (copy_done / copy_total) * 100.0
            print(f'\rcopying {copy_total / 1024.0 / 1024.0:.2f}Mb {src} to {dst} ... {t:.2f}%', end='', file=sys.stdout, flush=True)

        print(f" OK", file=sys.stdout, flush=True)

    except Exception as e:
        print(f'Exception: {src} to {dst}: {str(e)}')


def set_prio():
    try:
        proc = psutil.Process(os.getpid())
        proc.nice(psutil.IDLE_PRIORITY_CLASS)
        proc.ionice(psutil.IOPRIO_VERYLOW)
        proc.cpu_affinity([0])
    except Exception as e:
        print(f'priority: {e}')
    else:
        print(f'affinity/priority has been set to lowest')


def remove_temps():
    print(f'removing temps ... ', end='')
    temps = glob.glob(os.path.join(tempfile.gettempdir(), 'backup-tool', '*.btf'))
    for f in temps:
        if os.path.isfile(f):
            print(f'{f} ', end='')
            os.remove(f)


def setup_exiters():
    atexit.register(remove_temps)


if __name__ == '__main__':
    print(f'proc: {os.getpid()}')

    load_config()
    set_prio()
    setup_exiters()
    remove_temps()
    dirs = get_dir_setups()

    for root_path, dst_path in dirs:
        dest = os.path.join(get_root_dest(), dst_path)
        print(f'archive {root_path} => {dest}')

    for root_path, dst_path in dirs:
        dest = os.path.join(get_root_dest(), dst_path)

        make_directories(dest)
        print(f'working @ {root_path} => {dest}')

        if config['settings'].getboolean('erase_storage', False):
            erase_dir(dest)

        process_directory(dir=None, current_src=root_path, current_dst=dest)

        done_dirs.append(root_path)

    p_exit()
