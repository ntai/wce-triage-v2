"""String constants.
Once defined, it becomes immutable.
"""


class _const:

  class ConstError(TypeError):
    pass

  def __setattr__(self, name, value):
    if name in self.__dict__:
      raise self.ConstError
    self.__dict__[name] = value

  def __delattr__(self, name):
    if name in self.__dict__:
      raise self.ConstError
    raise NameError
  pass

const = _const()

const.wce_share="wce_share"
const.wce_payload="wce_payload"

# WCE setup consts
const.WCE_SERVER="WCE_SERVER"
const.WCE_DESKTOP="WCE_DESKTOP"

const.WCE_TRIAGE_DISK='WCE_TRIAGE_DISK'

# Triage ssid/password
const.TRIAGE_SSID = "TRIAGE_SSID"
const.TRIAGE_PASSWORD = "TRIAGE_PASSWORD"


const.TRIAGEUSER = 'TRIAGEUSER'
const.TRIAGEPASS = 'TRIAGEPASS'

#
const.GRUB_DISABLE_OS_PROBER = 'GRUB_DISABLE_OS_PROBER'


const.PATCHES = 'PATCHES'
const.server = 'server'
const.workstation = 'workstation'

#
const.true = 'true'

const.efi_image = 'efi_image'
const.partition_plan = 'partition_plan'
const.partition_map = 'partition_map'
const.clone = 'clone'
const.traditional = 'traditional'
const.triage = 'triage'
const.ext4_version = 'ext4_version'

const.ext4_version_1_42 = "1.42"
const.ext4_version_no_metadata_csum = const.ext4_version_1_42

const.forcepae = 'forcepae'
const.cmdline = 'cmdline'

# cmdline special value for removing vlaue
const._REMOVE_ = '_REMOVE_'
