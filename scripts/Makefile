
.PHONY: update clean client

update:
	#-sudo -H pip3 uninstall wce_triage
	sudo -H pip3 install --upgrade --no-cache-dir -i https://test.pypi.org/simple/ --no-deps wce_triage
	sudo rm -fr /usr/local/share/wce/wce-triage-ui/*
	cd /usr/local/share/wce/wce-triage-ui && wget -q -O - http://release.cleanwinner.com/wce/wce-triage-ui.tgz | tar xzf -


clean:
	sudo apt clean
	sudo apt autoclean
	sudo journalctl --vacuum-time=1m
	sudo truncate --size=0 /var/log/syslog
	sudo truncate --size=0 /var/log/auth.log
	sudo truncate --size=0 /var/log/dpgk.log
	sudo truncate --size=0 /var/log/kern.log
	sudo truncate --size=0 /var/log/alternatives.log
	sudo rm -f /var/log/Xorg.*
	sudo rm -f /var/log/apt/*
	sudo rm -fr /var/log/installer/*
	sudo rm -fr /root/Desktop
	sudo rm -fr /hoem/triage/.config/google-chrome
	sudo rm -f /var/cache/apt/pkgcache.bin /var/cache/apt/srcpkgcache.bin 
	sudo rm -f /var/lib/apt/lists/* > /dev/null 2>&1

client:
	sudo rsync -av --delete /usr/local/lib/python3.6/dist-packages/ /var/lib/netclient/wcetriage_amd64/usr/local/lib/python3.6/dist-packages/
	sudo rsync -av --delete /usr/local/share/wce/triage/ /var/lib/netclient/wcetriage_amd64/usr/local/share/wce/triage/
	sudo rsync -av --delete /usr/local/share/wce/wce-triage-ui/ /var/lib/netclient/wcetriage_amd64/usr/local/share/wce/wce-triage-ui/
	sudo rsync -av --delete /usr/local/lib/python3.6/dist-packages/ /var/lib/netclient/wcetriage_x32/usr/local/lib/python3.6/dist-packages/
	sudo rsync -av --delete /usr/local/share/wce/triage/ /var/lib/netclient/wcetriage_x32/usr/local/share/wce/triage/
	sudo rsync -av --delete /usr/local/share/wce/wce-triage-ui/ /var/lib/netclient/wcetriage_x32/usr/local/share/wce/wce-triage-ui/
