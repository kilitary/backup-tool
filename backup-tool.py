import os
import shutil
import sys
from os.path import join, getsize
import json
from pprint import pprint
from os import scandir
import configparser
from shutil import copytree
import psutil

config_file = "backup-tool.ini"
current_root = ''
config = configparser.ConfigParser()

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
    return []

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

def get_dir_setups():
    dirs = []
    for i, o in config["directories"].items():
        dirs.append((o, i))
    return dirs

def make_directories(dir):
    try:
        os.makedirs(dir, exist_ok=True)
    except IOError as e:
        print(f'exception while creating dir {dir}: {e.errno} {os.strerror(e.errno)}')

def get_root_dest():
    return config['settings']['dest']

def process_directory(dir=None, current_dst='', current_src=""):
    """
    copy directory (recursive)
    """
    global current_root
    
    dir = current_src if dir is None else dir
    
    try:
        dirs = scandir(dir)
    except Exception as e:
        pred(f'scandir: {e}')
        return
    
    print(f'{current_src} => {current_dst}')
    
    for entry in dirs:
        try:
            if entry.is_dir() and entry.name not in [".", ".."]:
                dest_dir = os.path.join(current_dst, entry.name)
                current_root = dest_dir
                
                assert dest_dir.count("z:") != 0, 'error: nocopy'
                
                src_dir = os.path.join(current_src, entry.name)
                copytree(src_dir, dest_dir, ignore=_logpath, dirs_exist_ok=True)
                # process_directory(dir=os.path.join(dir, entry.name), current_dst=dest_dir, current_src=src_dir)
            else:
                dest_dir = os.path.join(current_dst, dir[3:])
                
                assert dest_dir.count("z:") != 0, 'error: nocopy'
                
                make_directories(dest_dir)
                dest_file = os.path.join(current_dst, entry.name)
                print(f'copy {entry.path} to {dest_file}')
                copyfile(entry.path, dest_file)
        except IOError as e:
            print(f'exception while copying dir {dir}: {e.errno} {e.strerror}', e)
            if e.errno == 28:
                pred(f'storage exhaused')
                sys.exit(-1)
            continue

def copyfile(src, dst, buf_siz=1024 * 1024):
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
            # t = (copy_done / copy_total) * 100.0
        
        print(f" OK", file=sys.stdout, flush=True)
    
    except IOError as e:
        print(f'e: {src} to {dst}: code: {e.errno} msg: {os.strerror(e.errno)}')

def set_prio():
    try:
        p = psutil.Process(os.getpid())
        p.nice(psutil.IDLE_PRIORITY_CLASS)
        p.ionice(psutil.IOPRIO_VERYLOW)
        p.cpu_affinity([0])
    except Exception as e:
        print(f'priority: {e}')
    else:
        print(f'affinity/priority has been set to lowest')

if __name__ == '__main__':
    print(f'proc: {os.getpid()}')
    
    load_config()
    set_prio()
    
    dirs = get_dir_setups()
    for root_path, dst_path in dirs:
        dest = os.path.join(get_root_dest(), dst_path)
        
        # make_directories(dest)
        print(f'working @ {root_path} => {dest}')
        
        if config['settings'].getboolean('erase_storage', False):
            erase_dir(dest)
        
        process_directory(dir=None, current_src=root_path, current_dst=dest)
