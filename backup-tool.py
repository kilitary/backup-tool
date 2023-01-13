import os
import sys
from os.path import join, getsize
import json
from pprint import pprint
from os import scandir
import configparser


config_file = "backup-tool.ini"
current_root = ''
config = configparser.ConfigParser()

def pred(text):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(255, 0, 0, text))

def pgray(text):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(11, 110, 0, text))

def pgreen(text, send='\n'):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(11, 110, 110, text), end=send)

def pblue(text):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(111, 210, 110, text))

def pblack(text, send='\n'):
    print("\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(21, 25, 244, text), end=send)

def dump(data, exit=False):
    pprint(data)
    if exit:
        sys.exit()

def load_config():
    config.read(config_file)
    print(f'{config.sections()}')

def erase_storage():
    print(f'erase storage before')

def get_dir_setups():
    dirs = config['directories']['path'].split(',')
    dirs = [d.split("=") for d in dirs]
    return dirs

def make_directories(dir):
    try:
        os.makedirs(dir, exist_ok=True)
    except Exception as e:
        print(f'exception while creating dir {dir}: {e}')

def get_root():
    return config['settings']['dest']

def process_directory(dir, prefix=''):
    """
    copy directory (recursive)
    """
    global current_root
    dirs = scandir(dir)
    for entry in dirs:
        try:
            if entry.is_dir() and entry.name not in [".", ".."]:
                dest_dir = os.path.join(current_root, entry.name)
                print(f'creating {dest_dir}')
                make_directories(dest_dir)
                current_root = os.path.join(dest_dir, entry.name)
                process_directory(os.path.join(dir, entry.name))
            else:
                dest_dir = os.path.join(get_root(), prefix, dir[3:])
                make_directories(dest_dir)
                assert os.path.isdir(dest_dir), f'not a dir {dest_dir}'
                dest_file = os.path.join(current_root, entry.path[3:])
                print(f'copy {entry.path} to {dest_file}')
                copyfile(entry.path, dest_file)
        except Exception as e:
            raise ValueError(e)

def copyfile(src, dst, buf_siz=1024 * 1024):
    """
    Copy a file
    """
    if os.path.exists(dst):
        os.unlink(dst)
    copy_total = os.path.getsize(src)
    copy_done = 0
    f = src.replace("\\", '\\')
    d = dst.replace("\\", '\\')
    # print(f'{f} {d}')
    src_f = open(f, mode="rb")
    dst_f = open(d, mode='xb')
    print(f'copying {copy_total / 1024.0 / 1024.0:.2f}Mb {src} to {dst} ... ', end='', file=sys.stdout, flush=True)
    while True:
        copy_buffer = src_f.read(buf_siz)
        if not copy_buffer:
            break
        copy_done += dst_f.write(copy_buffer)
        # t = (copy_done / copy_total) * 100.0
    print(f" OK", file=sys.stdout, flush=True)

if __name__ == '__main__':
    load_config()
    print(f'proc: {os.getpid()}')
    
    if config['settings'].getboolean('erase_storage', False):
        erase_storage()
    
    dirs = get_dir_setups()
    for root_path, dst_path in dirs:
        dest = os.path.join(get_root(), dst_path)
        make_directories(dest)
        print(f'working @ {root_path} => {dest}')
        current_root = root_path
        process_directory(dir=root_path, prefix=dst_path)
