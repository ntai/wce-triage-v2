
import os, psutil, datetime, json, traceback
from wce_triage.lib.util import *

IMAGE_META_JSON_FILE = ".disk_image_type.json"

# gets the potential directories to look for disk images
def get_maybe_disk_image_directories():
  dirs = []

  for part in psutil.disk_partitions():
    for subdir in [ ".", "image", "var/lib/www", "usr/local/share/wce" ]:
      path = os.path.join(part.mountpoint, subdir, 'wce-disk-images')
      if os.path.exists(path) and os.path.isdir(path):
        dirs.append(path)
        pass
      pass
    pass

  # On network boot, there is no physical disks. I could go after
  # moutns but there is only one location possible for netboot+NFS.
  wce_images = "/usr/local/share/wce/wce-disk-images"
  if os.path.exists(wce_images) and os.path.isdir(wce_images) and wce_images not in dirs:
    dirs.append(wce_images)
    pass

  return dirs

#
# 
#
def get_disk_images():
  '''scans the known drectories for disk image and returns the list of disk images

    :arg none

    :returns: list of dict instances. 
      mtime: file modify time
      restoreType: keyword for restore type. [wce|wce-16|triage|clone]
                   The restore type is nothing more than the name of directory, and
                   should match exactly to the restore type.
      name: filename - this is shown to the user.
      size: file size
      fullpath: the full path.

    ..note the entries are deduped by the filename so if two directories
           contain the same file name, only one is pikced.
  '''
  # Dedup the same file name
  images = {}
  for subdir in get_maybe_disk_image_directories():
    for direntry in os.listdir(subdir):
      # Anything starting with "." is ignored
      if direntry[0:1] == '.':
        continue

      catalog_dir = os.path.join(subdir, direntry)
      image_meta_file = os.path.join(catalog_dir, IMAGE_META_JSON_FILE)
      if not os.path.exists(image_meta_file) or not os.path.isfile(image_meta_file):
        continue

      if direntry.endswith(".partclone.gz"):
        images[direntry] = (direntry, "", catalog_dir)
        pass

      if os.path.isdir(catalog_dir):
        for direntryinsubdir in os.listdir(catalog_dir):
          # Anything starting with "." is ignored
          if direntryinsubdir[0:1] == '.':
            continue
          if direntryinsubdir.endswith(".partclone.gz"):
            images[direntryinsubdir] = (direntryinsubdir, direntry, os.path.join(catalog_dir, direntryinsubdir))
            pass
          pass
        pass
      pass
    pass

  result = []
  for filename, image in images.items():
    fname, subdir, fullpath = image
    filestat = os.stat(fullpath)
    mtime = datetime.datetime.fromtimestamp(filestat.st_mtime)
    fattr = { "mtime": mtime.strftime('%Y-%m-%d %H:%M'),
              "restoreType" : subdir,
              "name": filename,
              "fullpath": fullpath,
              "size": filestat.st_size }
    result.append(fattr)
    pass

  return result


def read_disk_image_types():
  '''scans the known drectories for disk image and returns the list of disk image types

    :arg none

    :returns: list of dict instances which is .disk_image_type.json file in the directory. 

  '''
  image_metas = []
  for subdir in get_maybe_disk_image_directories():
    for direntry in os.listdir(subdir):
      catalog_dir = os.path.join(subdir, direntry)
      image_meta = read_disk_image_type(catalog_dir)
      if image_meta:
        image_metas.append(image_meta)
        pass
      pass
    pass
  return image_metas


def read_disk_image_type(catalog_dir):
  '''reads the disk image type file from the directory

    :arg dir

    :returns: a dict instance from the image-meta

  '''
  result = None
  try:
    image_meta_file = os.path.join(catalog_dir, IMAGE_META_JSON_FILE)
    if not os.path.exists(image_meta_file) or not os.path.isfile(image_meta_file):
      return None
  
    with open(image_meta_file) as meta_file:
      result = json.load(meta_file)
      pass
    pass
  except json.decoder.JSONDecodeError:
    get_triage_logger().debug('catalog_dir %s: JSON parse error. Check the contents.' % catalog_dir);
    pass
  except:
    # If anything goes wrong, just ignore the directory.
    get_triage_logger().debug('catalog_dir %s: %s' % (catalog_dir, traceback.format_exc()))
    pass
  # 
  if result:
    result["catalogDirectory"] = catalog_dir
    pass
  
  return result


def make_disk_image_name(destdir, inname, filesystem='ext4'):
  image_meta = read_disk_image_type(destdir)
  if image_meta is None:
    if inname == None:
      raise Exception("Directory %s does not have '" + IMAGE_META_JSON_FILE + "' file.")
    return inname

  imagename = image_meta["filestem"]
  if not imagename:
    imagename = inname
    pass
    
  if image_meta.get("timestamp", False):
    timestamp = datetime.date.today().isoformat()
    imagename = imagename + "-" + timestamp
    pass
  # Right now, this is making ext4
  imagename = imagename + ".%s.partclone.gz" % filesystem
  return os.path.join(destdir, imagename)


def get_file_system_from_source(source):
  filesystem_ext = None
  tail = ".partclone.gz"
  if source.endswith(tail):
    source = source[:-len(tail)]
  else:
    return None
  try:
    filesystem_ext = os.path.splitext(source)[1][1:]
  except:
    pass

  if filesystem_ext in ['ext4', 'ext3', 'fat32', 'vfat', 'fat16']:
    return filesystem_ext
  return None


#
if __name__ == "__main__":
  print(read_disk_image_types())
  print(get_disk_images())
  print(get_file_system_from_source("a.ext4.partclone.gz"))
  print(get_file_system_from_source("a.ext4.partclone"))
  print(get_file_system_from_source("a.partclone.gz"))
  pass
