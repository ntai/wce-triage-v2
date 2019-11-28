
.PHONY: update update-backend clean client

# v0.2 UI
# https://drive.google.com/uc?export=download&id=1eNzcClc_rLebtwhR2KDfZbMA9c9W_P2Y
#
# v0.3 UI
# https://drive.google.com/uc?export=download&?id=1Rjj9vD02Gid99qDrt3pvs6pitK0lBmyU

update: update-backend update-frontend

update-backend:
	sudo -H pip3 install --upgrade --no-cache-dir -i https://test.pypi.org/simple/ wce_triage

update-frontend:
	sudo rm -fr /usr/local/share/wce/wce-triage-ui/*
	cd /usr/local/share/wce/wce-triage-ui && curl -L -o - 'https://drive.google.com/uc?export=download&id=1Rjj9vD02Gid99qDrt3pvs6pitK0lBmyU' | tar xzf -
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


cleanwinner:
	cd /usr/local/share/wce/wce-triage-ui && curl -L -o - 'http://release.cleanwinner.com/wce/wce-triage-ui.tgz' | tar xzf -

