import os
import sys
import traceback
import linux
import stat
import tarfile
import uuid
from pathlib import Path


def create_container_root():
    image_directory = "/home/utsav/Projects"

    files = os.listdir(image_directory)

    ext_list = ['tar', 'gz', 'zip']
    def intersection(lst1, lst2):
        return list(set(lst1) & set(lst2))

    base_images = list(filter(lambda f: intersection(Path(f).suffixes, ext_list)!=0, files))

    ###Extract into another directory

    file = "/home/utsav/Projects/images_tar/ubuntu-base-18.04.4-base-amd64.tar.gz"

    target_path = "/home/utsav/Projects/images/Ubuntu"
    
    if os.path.isdir(target_path):
        pass
    else:
        os.mkdir(target_path)

    tar = tarfile.open(file)
    tar.extractall(target_path)
    tar.close()

    return target_path


# Mount private the root mount and do it recursively to avaoid umounting imp stuff like /dev/pts
def makedev(dev_path):
    
    pid = os.getpid() # Another way to add symlink prolly

    for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
        os.symlink('/proc/self/fd/%d' % i, os.path.join(dev_path, dev)) # self bc a symlink to the current process
    os.symlink('/proc/self/fd', os.path.join(dev_path, 'fd'))

    # Add extra devices
    DEVICES = {
        'null': (stat.S_IFCHR, 1, 3),  
        'zero': (stat.S_IFCHR, 1, 5), 
        'random': (stat.S_IFCHR, 1, 8), 
        'urandom': (stat.S_IFCHR, 1, 9), 
        'tty': (stat.S_IFCHR, 5, 0), 
        'console': (stat.S_IFCHR, 136, 1), 
        'full': (stat.S_IFCHR, 1, 7), 
        }

    for device, (dev_type, major, minor) in DEVICES.iteritems():
        os.mknod(os.path.join(dev_path, device), 0o666 | dev_type, os.makedev(major, minor))


def contain(cmd, cid):
    # linux.unshare(linux.CLONE_NEWNS)  # create a new mount namespace
    # linux.unshare(linux.CLONE_NEWUTS) # create a new uts namespace

    # linux.sethostname(cid)

    ### Use Linux.clone in run() before fork and uncomment the above lines

    linux.mount(None, '/', None, linux.MS_REC | linux.MS_PRIVATE, None)

    new_root = create_container_root()

    print("New Root created.")
    
    ### When using an already extracted image
    # linux.umount(os.path.join(new_root, 'proc'))
    # linux.umount(os.path.join(new_root, 'sys'))
    
    linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
    linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
    linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs', linux.MS_STRICTATIME | linux.MS_NOSUID, 'mode=755')

    #Add Basic Devices
    devs = os.path.join(new_root, 'dev', 'pts')
    if os.path.exists:
        pass
    else:
        os.makedirs(devs)
        linux.mount('devpts', devs, 'devpts', 0, '')
    
    makedev(os.path.join(new_root, 'dev'))

    os.chroot(new_root)
    os.chdir("/")

    os.execvp(cmd[0], cmd)


def run(cmd):
    cid = str(uuid.uuid4())

    linux.unshare(linux.CLONE_NEWNS)  # create a new mount namespace
    linux.unshare(linux.CLONE_NEWUTS) # create a new uts namespace
    linux.unshare(linux.CLONE_NEWNET) # create a new n/w namespace

    linux.sethostname(cid)

    pid = os.fork()

    if pid == 0:
        try:
            contain(cmd, cid)
        except Exception:
            traceback.print_exc()
            os._exit(1)
    elif pid < 0:
        raise Exception("Fork Error")

    _, status = os.waitpid(pid, 0)
    print(str(pid) + " exited with status " + str(status))


def main():
    print("*Cmds and Args*")

    if len(sys.argv) <= 1:
        # raise Exception("Too less arguments.")
        print("Too less arguments.")
    elif sys.argv[1] != "run":
        print("Invalid command")
        os._exit(1)

    run(sys.argv[2:])


if __name__ == "__main__":
    main()