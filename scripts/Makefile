
.PHONY: update clean client

update:
	#-sudo -H pip3 uninstall wce_triage
	sudo -H pip3 install --upgrade --no-cache-dir -i https://test.pypi.org/simple/ wce_triage
	sudo rm -fr /usr/local/share/wce/wce-triage-ui/*
	cd /usr/local/share/wce/wce-triage-ui && curl -L -o - "https://drive.google.com/uc?export=download&id=1eNzcClc_rLebtwhR2KDfZbMA9c9W_P2Y" | tar xzf -
	python3 -m wce_triage.setup.update_share

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
	python3 -m wce_triage.setup.update_client
