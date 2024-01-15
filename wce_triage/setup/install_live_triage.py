#!/usr/bin/python3
#
# This is for Triage USB stick on mini system
#
import subprocess

if __name__ == "__main__":
  LIVE_TRIAGE="wce-live-triage"
  tmp_live_triage = "/tmp/"+LIVE_TRIAGE
  real_live_triage = "/usr/local/bin/"+LIVE_TRIAGE

  live_triage_script = open(tmp_live_triage, "w")
  live_triage_script.write('''''')
  live_triage_script.close()

  subprocess.run(['sudo', '-H', 'install', '-m', '0755', tmp_live_triage, real_live_triage])
  subprocess.run(['sudo', '-H', 'ln', '-s', real_live_triage, "/autorun"])
  pass

