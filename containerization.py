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

    base_images = list(filter(lambda f: intersection(
        Path(f).suffixes, ext_list) != 0, files))

    # Extract into another directory

    file = "/home/utsav/Projects/images_tar/ubuntu-base-18.04.4-base-amd64.tar.gz"

    target_path = "/home/utsav/Projects/images/ubuntu-base-18.04.4-base-amd64"

    if not os.path.isdir(target_path):
        os.mkdir(target_path)
    # else:
    #     os.removedirs(target_path)

    tar = tarfile.open(file)
    tar.extractall(target_path)
    tar.close()

    return target_path


BASE_DIR_CGROUP = '/sys/fs/cgroup'


def _set_cgroup_cpu(cid):
    base_dir_cpu = os.path.join(BASE_DIR_CGROUP, 'cpu')
    container_dir = os.path.join(base_dir_cpu, 'docker_clone', cid)

    # Put the container to the newly created cpu cgroup
    if not os.path.exists(container_dir):
        os.makedirs(container_dir)

    task_file = os.path.join(container_dir, 'tasks')
    open(task_file, 'w').write(str(os.getpid()))

    cpu_shares = input('Insert memory to be allocated: ')

    # set cpu_shares
    if cpu_shares != 0:
        file = os.path.join(container_dir, 'cpu.shares')
        open(file, 'w').write(str(cpu_shares))


def _set_cgroup_memory(cid):
    base_dir_mem = os.path.join(BASE_DIR_CGROUP, 'memory')
    container_dir = os.path.join(base_dir_mem, 'docker_clone', cid)

    # Put the container to the newly created memory cgroup
    if not os.path.exists(container_dir):
        os.makedirs(container_dir)

    task_file = os.path.join(container_dir, 'tasks')
    open(task_file, 'w').write(str(os.getpid()))

    # Ask for memory
    memory = input("Insert memory limit in bytes (k, m, g): ")

    if memory != 0:
        mem_limit_file = os.path.join(container_dir, 'memory.limit_in_bytes')
        open(mem_limit_file, 'w').write(str(memory))

    # print("Insert memory swap limit in bytes (k, m, g)")
    # print("(Memory plus swap): ")
    # memory_swap = input()

    # if memory != 0:
    #     memswap_limit_file = os.path.join(container_dir, 'memory.memsw.limit_in_bytes')
    #     open(memswap_limit_file, 'w').write(str(memory_swap))

# Mount private the root mount and do it recursively to avoid umounting imp stuff like /dev/pts
def _makedev(dev_path):
    pid = os.getpid()  # Another way to add symlink prolly

    for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
        # self bc a symlink to the current process
        os.symlink('/proc/self/fd/%d' % i, os.path.join(dev_path, dev))
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
        os.mknod(os.path.join(dev_path, device), 0o666 |
                 dev_type, os.makedev(major, minor))


def contain(cmd, cid):
    _set_cgroup_cpu(cid)
    _set_cgroup_memory(cid)

    linux.unshare(linux.CLONE_NEWNS)  # create a new mount namespace
    linux.unshare(linux.CLONE_NEWUTS) # create a new uts namespace
    linux.unshare(linux.CLONE_NEWNET) # create a new n/w namespace

    linux.sethostname(cid)

    # Use linux.clone in run() before fork and uncomment the above lines

    linux.mount(None, '/', None, linux.MS_REC | linux.MS_PRIVATE, None)

    new_root = create_container_root()

    print("New Root created.")

    # When using an already extracted image
    # linux.umount(os.path.join(new_root, 'proc'))
    # linux.umount(os.path.join(new_root, 'sys'))

    linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
    linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
    linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs', linux.MS_STRICTATIME | linux.MS_NOSUID, 'mode=755')

    # Add Basic Devices
    devs = os.path.join(new_root, 'dev', 'pts')
    if os.path.exists:
        pass
    else:
        os.makedirs(devs)
        linux.mount('devpts', devs, 'devpts', 0, '')

    _makedev(os.path.join(new_root, 'dev'))

    os.chroot(new_root)
    os.chdir("/")

    os.execvp(cmd[0], cmd)


def run(cmd):
    cid = str(uuid.uuid4())

    # linux.unshare(linux.CLONE_NEWNS)  # create a new mount namespace
    # linux.unshare(linux.CLONE_NEWUTS)  # create a new uts namespace
    # linux.unshare(linux.CLONE_NEWNET)  # create a new n/w namespace
    # linux.unshare(linux.CLONE_NEWPID) 

    # linux.sethostname(cid)

    flags = linux.CLONE_NEWPID | linux.CLONE_NEWNS | linux.CLONE_NEWUTS
    callback = (cmd, cid)
    pid = linux.clone(contain, flags, callback)

    # pid = os.fork()

    # if pid == 0:
    #     try:
    #         contain(cmd, cid)
    #     except Exception:
    #         traceback.print_exc()
    #         os._exit(1)
    # elif pid < 0:
    #     raise Exception("Fork Error")

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