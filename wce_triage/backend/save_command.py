from .threaded_command import ThreadedCommandRunner
from .emitter import Emitter
from queue import SimpleQueue
tlog = get_triage_logger()
#
#
class SaveCommandRunner(ThreadedCommandRunner):
    queue: SimpleQueue

    def __init__(self, tag, end_unc, *args):
        self.queue = SimpleQueue()
        super().__init__("saveimage", None, *args)
        pass

    def run(self):
        while True:
            devname, saveType, destdir, partid = self.queue.get()

            if saveType is None:
                tlog.info("saveimage - image type is not given.")
                return json_response({}, status=HTTP_SERVICE_UNAVAILABLE)

            emit("saveimage", {"device": devname, "runStatus": "", "totalEstimate": 0, "tasks": []})

        target = None
        for disk in self.disk_portal.disks:
            if disk.device_name == devname:
                target = disk
                break
            pass

        if target is None:
            tlog.info("No such disk " + devname)
            return json_response({}, status=HTTP_SERVICE_UNAVAILABLE)

        disk = self.disk_portal.find_disk_by_device_name(devname)
        lister = PartitionLister(disk)
        lister.execute()

        part = disk.find_partition(partid)
        if part is None:
            part = disk.find_partition_by_file_system('ext4')
            pass

        if part is None:
            for partition in disk.partitions:
                tlog.debug(str(partition))
                pass
            Emitter.alert("Device %s has no EXT4 partition for imaging." % disk.device_name)
            return

        partition_id = disk.get_partition_id(part)
        if partition_id is None:
            Emitter.alert("Partition %s has not valid ID." % part.device_name)
            return

        # saveType is a single word coming back from read_disk_image_types()
        image_type = None
        for _type in read_disk_image_types():
            if _type["id"] == saveType:
                image_type = _type
                break
            pass
        if image_type is None:
            Emitter.alert("Image type %s is not known." % saveType)
            return

        destdir = image_type.get('catalogDirectory')
        if destdir is None:
            Emitter.alert("Imaging type info %s does not include the catalog directory." % image_type.get("id"))
            return

        # save image runs its own course, and output will be monitored by a call back
        args = ['python3', '-m', 'wce_triage.ops.create_image_runner', devname, str(partition_id), destdir]
        tlog.info("saveimage - " + " ".join(args))

        threading.Thread(target=self.run_save_disk_image,
                         daemon=True,
                         args=[self] + args)

        return json_response({})

    def run_save_disk_image(self, *args):

        self.saver = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        runner = "saver"

        while self.restore.returncode is None:
            self.restore.poll()

            line = self.restore.stdout.readline()
            if line == b'' or line is None:
                break
            if line.strip() != '':
                tlog.debug("%s: '%s'" % (runner, line))
                try:
                    packet = json.loads(line)
                    Emitter.send(packet['event'], packet['message'])
                except Exception as exc:
                    tlog.info("%s: BAD LINE '%s'\n%s" % (runner, line, traceback.format_exc()))
                    Emitter.note(line)
                    pass
            else:
                Emitter.note(line)
                pass
            pass

        if self.restore.returncode is not 0:
            Emitter.note("Restore failed with error code %d" % self.restore.returncode)
            pass
        Emitter.send(runner, {"device": ''})
        self.saver = None
        pass



    def ending(self):
        Emitter.send(self.tag, {"device": ''})
        super().ending()
        pass

    pass


threading.Thread(target=self.run_save_disk_image,
                 daemon=True,
                 args=[self] + args)

return json_response({})


def run_save_disk_image(self, *args):
    self.saver = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    runner = "saver"

    while self.restore.returncode is None:
        self.restore.poll()

        line = self.restore.stdout.readline()
        if line == b'' or line is None:
            break
        if line.strip() != '':
            tlog.debug("%s: '%s'" % (runner, line))
            try:
                packet = json.loads(line)
                Emitter.send(packet['event'], packet['message'])
            except Exception as exc:
                tlog.info("%s: BAD LINE '%s'\n%s" % (runner, line, traceback.format_exc()))
                Emitter.note(line)
                pass
        else:
            Emitter.note(line)
            pass
        pass

    if self.restore.returncode is not 0:
        Emitter.note("Restore failed with error code %d" % self.restore.returncode)
        pass
    Emitter.send(runner, {"device": ''})
    self.saver = None
    pass
