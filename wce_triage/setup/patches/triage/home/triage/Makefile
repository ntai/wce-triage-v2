
.PHONY: update

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
