# Firefox on super vanilla Ubuntu does not work which is based on 
# snap, so install binary one.

import subprocess

if __name__ == "__main__":
    subprocess.run('sudo -H snap remove firefox', shell=True)
    # To use add-apt-repository, need this package
    subprocess.run('sudo -H apt install -y software-properties-common --no-install-recommends', shell=True)
    subprocess.run("sudo -H add-apt-repository -y ppa:mozillateam/ppa", shell=True)
    with open('/tmp/mozilla-firefox', 'w') as pref:
        pref.write("""
Package: *
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 1001
""")
    subprocess.run("sudo install -m 644 /tmp/mozilla-firefox /etc/apt/preferences.d/mozilla-firefox", shell=True)
    # echo 'Unattended-Upgrade::Allowed-Origins:: "LP-PPA-mozillateam:${distro_codename}";' | sudo tee /etc/apt/apt.conf.d/51unattended-upgrades-firefox
    subprocess.run("sudo apt install -y firefox --no-install-recommends", shell=True)
    pass





