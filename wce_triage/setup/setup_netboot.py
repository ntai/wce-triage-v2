#!/usr/bin/env python3
"""
PXE Boot Server Setup Script for Ubuntu 24.04 LTS
Matches the existing WCE PXE implementation paths and structure.
"""

import os
import sys
import subprocess
import socket
import shutil
import argparse
import re
import stat
from pathlib import Path
from typing import List, Tuple, Optional
import distutils.file_util

class PXEServerSetup:
    def __init__(self, server_ip: str, network_interface: str, dhcp_range: str, gateway: str):
        self.server_ip = server_ip
        self.network_interface = network_interface
        self.dhcp_range = dhcp_range
        self.gateway = gateway
        self.subnet = self._calculate_subnet()
        
        # Directory paths - matching the existing implementation
        self.netclient_dir = Path("/var/lib/netclient")
        self.netboot_dir = Path("/var/lib/netboot")
        self.pxelinux_cfg_dir = self.netboot_dir / "pxelinux.cfg"
        self.wce_boot_dir = self.netboot_dir / "wce"
        self.wce_amd64_dir = self.netboot_dir / "wce_amd64"
        self.wce_x32_dir = self.netboot_dir / "wce_x32"
        
        # NFS root directories for architectures
        self.wcetriage_amd64_dir = self.netclient_dir / "wcetriage_amd64"
        self.wcetriage_x32_dir = self.netclient_dir / "wcetriage_x32"
        
        # Required packages
        self.packages = [
            "tftpd-hpa", "nfs-kernel-server", "dnsmasq",
            "syslinux-common", "pxelinux", "debootstrap"
        ]
        
        # Service names
        self.services = ["tftpd-hpa", "nfs-kernel-server", "dnsmasq"]

    def _calculate_subnet(self) -> str:
        """Calculate subnet from server IP (assumes /24)"""
        ip_parts = self.server_ip.split('.')
        return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0"

    def run_command(self, command: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
        """Run a system command with error handling"""
        try:
            result = subprocess.run(command, check=check, capture_output=capture_output, text=True)
            if capture_output:
                print(f"✓ Command succeeded: {' '.join(command)}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"✗ Command failed: {' '.join(command)}")
            print(f"  Error: {e}")
            if capture_output and e.stdout:
                print(f"  Output: {e.stdout}")
            if capture_output and e.stderr:
                print(f"  Error output: {e.stderr}")
            raise

    def check_root(self) -> bool:
        """Check if running as root"""
        return os.geteuid() == 0

    def get_os_version(self) -> str:
        """Get Ubuntu version from /etc/os-release"""
        version_id_re = re.compile(r'VERSION_ID=\"(\d+\.\d+)\"')
        with open("/etc/os-release") as osrel:
            match = version_id_re.search(osrel.read(), re.MULTILINE)
            if match:
                return match.group(1)
            else:
                return "24.04"  # Default fallback

    def update_package_list(self):
        """Update package list"""
        print("📦 Updating package list...")
        self.run_command(["apt", "update"])

    def install_packages(self):
        """Install required packages if not already installed"""
        print("📦 Installing required packages...")
        
        # Check which packages are already installed
        installed_packages = set()
        try:
            result = self.run_command(["dpkg", "-l"] + self.packages, check=False, capture_output=True)
            for line in result.stdout.split('\n'):
                if line.startswith('ii '):
                    package_name = line.split()[1]
                    if package_name in self.packages:
                        installed_packages.add(package_name)
        except:
            pass

        packages_to_install = [pkg for pkg in self.packages if pkg not in installed_packages]
        
        if packages_to_install:
            print(f"Installing: {', '.join(packages_to_install)}")
            self.run_command(["apt", "install", "-y"] + packages_to_install)
        else:
            print("✓ All required packages already installed")

    def create_directories(self):
        """Create required directories with proper permissions"""
        print("📁 Creating directory structure...")
        
        directories = [
            self.netclient_dir,
            self.netboot_dir,
            self.pxelinux_cfg_dir,
            self.wce_boot_dir,
            self.wce_amd64_dir,
            self.wce_x32_dir,
            self.wcetriage_amd64_dir,
            self.wcetriage_x32_dir
        ]
        
        for directory in directories:
            if not directory.exists():
                print(f"Creating directory: {directory}")
                directory.mkdir(parents=True, exist_ok=True)
                os.chmod(directory, 0o755)
            else:
                print(f"✓ Directory already exists: {directory}")

    def configure_tftp(self):
        """Configure TFTP server to use /var/lib/netboot"""
        print("🌐 Configuring TFTP server...")
        
        config_content = """# /etc/default/tftpd-hpa
TFTP_USERNAME="tftp"
TFTP_DIRECTORY="/var/lib/netboot"
TFTP_ADDRESS=":69"
TFTP_OPTIONS="--secure"
"""
        config_file = Path("/etc/default/tftpd-hpa")
        
        if not config_file.exists() or config_file.read_text() != config_content:
            print("Writing TFTP configuration...")
            config_file.write_text(config_content)
        else:
            print("✓ TFTP configuration already correct")

    def setup_pxe_files(self):
        """Set up PXE boot files - copying from syslinux modules"""
        print("🥾 Setting up PXE boot files...")
        
        # Copy pxelinux.0
        pxelinux_src = "/usr/lib/PXELINUX/pxelinux.0"
        pxelinux_dst = self.netboot_dir / "pxelinux.0"
        
        if Path(pxelinux_src).exists():
            if not pxelinux_dst.exists() or os.path.getmtime(pxelinux_src) > os.path.getmtime(pxelinux_dst):
                print(f"Copying {pxelinux_src}")
                distutils.file_util.copy_file(pxelinux_src, str(pxelinux_dst), update=True)
            else:
                print("✓ pxelinux.0 already up to date")
        else:
            print(f"⚠ Warning: {pxelinux_src} not found")
        
        # Copy all syslinux modules
        moduledir = Path("/usr/lib/syslinux/modules/bios")
        if moduledir.exists():
            for module_file in moduledir.iterdir():
                if module_file.is_file():
                    dest_file = self.netboot_dir / module_file.name
                    if not dest_file.exists() or os.path.getmtime(module_file) > os.path.getmtime(dest_file):
                        print(f"Copying {module_file.name}")
                        distutils.file_util.copy_file(str(module_file), str(dest_file), update=True)
        else:
            print(f"⚠ Warning: {moduledir} not found")

    def copy_kernel_files(self):
        """Copy kernel and initrd files based on Ubuntu version"""
        print("🐧 Copying kernel files...")
        
        os_version = self.get_os_version()
        print(f"Detected Ubuntu version: {os_version}")
        
        # Kernel file mappings based on Ubuntu version
        kernel_files = {
            "18.04": [('/vmlinuz', '/var/lib/netboot/wce/vmlinuz'),
                     ('/initrd.img', '/var/lib/netboot/wce/initrd.img')],
            "20.04": [('/boot/vmlinuz', '/var/lib/netboot/wce/vmlinuz'),
                     ('/boot/initrd.img', '/var/lib/netboot/wce/initrd.img')],
            "22.04": [('/boot/vmlinuz', '/var/lib/netboot/wce/vmlinuz'),
                     ('/boot/initrd.img', '/var/lib/netboot/wce/initrd.img')],
            "24.04": [('/boot/vmlinuz', '/var/lib/netboot/wce/vmlinuz'),
                     ('/boot/initrd.img', '/var/lib/netboot/wce/initrd.img')],
            "26.04": [('/boot/vmlinuz', '/var/lib/netboot/wce/vmlinuz'),
                      ('/boot/initrd.img', '/var/lib/netboot/wce/initrd.img')],
        }
        
        if os_version not in kernel_files:
            print(f"⚠ Unsupported Ubuntu version: {os_version}")
            print("Using 24.04 defaults")
            os_version = "24.04"
        
        for src, dest in kernel_files[os_version]:
            if Path(src).exists():
                if not Path(dest).exists() or os.path.getmtime(src) > os.path.getmtime(dest):
                    print(f"Copying {src} to {dest}")
                    distutils.file_util.copy_file(src, dest, update=True)
                    os.chmod(dest, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                else:
                    print(f"✓ {dest} already up to date")
            else:
                print(f"⚠ Warning: {src} not found")

    def create_pxe_config(self):
        """Create PXE boot configuration matching the WCE format"""
        print("⚙ Creating PXE boot configuration...")
        
        pxelinux_cfg_default = f'''DEFAULT vesamenu.c32
TIMEOUT 100
TOTALTIMEOUT 600
PROMPT 0
NOESCAPE 1
ALLOWOPTIONS 1
# MENU BACKGROUND wceboot2.png
MENU MARGEIN 5
MENU TITLE WCE PXE Triage
LABEL WCE Triage 64bit
  MENU DEFAULT
  MENU LABEL WCE ^Triage
  KERNEL wce_amd64/vmlinuz
  APPEND initrd=wce_amd64/initrd.img hostname=bionic nosplash noswap boot=nfs netboot=nfs nfsroot={self.server_ip}:/var/lib/netclient/wcetriage_amd64 acpi_enforce_resources=lax edd=on ip=dhcp aufs=tmpfs ---
  TEXT HELP
  WCE Triage 64bit (amd64)
  ENDTEXT
LABEL WCE Triage 32bit
  MENU LABEL WCE ^32 bit Triage
  KERNEL wce_x32/vmlinuz
  APPEND initrd=wce_x32/initrd.img hostname=bionic nosplash noswap boot=nfs netboot=nfs nfsroot={self.server_ip}:/var/lib/netclient/wcetriage_x32 acpi_enforce_resources=lax edd=on ip=dhcp aufs=tmpfs ---
  TEXT HELP
  WCE Triage 32bit (x86_32)
  ENDTEXT
Label Local
  MENU LABEL Local operating system in harddrive (if available)
  KERNEL chain.c32
  APPEND sda1
  TEXT HELP
  Boot local OS from first hard disk if it's available
  ENDTEXT
'''
        
        config_file = self.pxelinux_cfg_dir / "default"
        
        if not config_file.exists() or config_file.read_text() != pxelinux_cfg_default:
            print("Writing PXE boot configuration...")
            with open(config_file, 'w') as pxe_menu:
                pxe_menu.write(pxelinux_cfg_default)
        else:
            print("✓ PXE boot configuration already correct")

    def configure_nfs(self):
        """Configure NFS server for WCE paths"""
        print("📂 Configuring NFS server...")
        
        exports_file = Path("/etc/exports")
        export_lines = [
            f"/var/lib/netclient/wcetriage_amd64 *(rw,sync,no_subtree_check,no_root_squash)",
            f"/var/lib/netclient/wcetriage_x32 *(rw,sync,no_subtree_check,no_root_squash)"
        ]
        
        # Read current exports
        current_exports = []
        if exports_file.exists():
            current_exports = exports_file.read_text().strip().split('\n')
        
        # Check if our export lines already exist
        lines_to_add = []
        for export_line in export_lines:
            if export_line not in current_exports:
                lines_to_add.append(export_line)
        
        if lines_to_add:
            print("Adding NFS exports...")
            with exports_file.open('a') as f:
                for line in lines_to_add:
                    f.write(f"\n{line}\n")
        else:
            print("✓ NFS exports already configured")

    def configure_dnsmasq(self):
        """Configure dnsmasq for PXE boot instead of separate DHCP server"""
        print("🌐 Configuring dnsmasq for PXE boot...")
        
        # Parse DHCP range
        range_start, range_end = self.dhcp_range.split('-')
        
        dnsmasq_config = f"""# dnsmasq configuration for PXE boot
interface={self.network_interface}
bind-interfaces
dhcp-range={range_start},{range_end},12h
dhcp-option=3,{self.gateway}
dhcp-option=6,8.8.8.8,8.8.4.4

# PXE boot settings
dhcp-boot=pxelinux.0,pxeserver,{self.server_ip}
enable-tftp
tftp-root=/var/lib/netboot

# Disable DNS for this instance
port=0
"""
        
        dnsmasq_config_file = Path("/etc/dnsmasq.d/pxe-boot.conf")
        
        # Create dnsmasq.d directory if it doesn't exist
        dnsmasq_config_file.parent.mkdir(exist_ok=True)
        
        if not dnsmasq_config_file.exists() or dnsmasq_config_file.read_text() != dnsmasq_config:
            print("Writing dnsmasq PXE configuration...")
            dnsmasq_config_file.write_text(dnsmasq_config)
        else:
            print("✓ dnsmasq configuration already correct")

    def setup_basic_rootfs(self, arch: str = "amd64"):
        """Set up a basic root filesystem for the specified architecture"""
        print(f"🗂 Setting up basic root filesystem for {arch}...")
        
        if arch == "amd64":
            rootfs_dir = self.wcetriage_amd64_dir
            debootstrap_arch = "amd64"
        elif arch == "x32" or arch == "i386":
            rootfs_dir = self.wcetriage_x32_dir
            debootstrap_arch = "i386"
        else:
            print(f"⚠ Unsupported architecture: {arch}")
            return
        
        # Check if rootfs already has content
        if any(rootfs_dir.iterdir()):
            print(f"✓ Root filesystem for {arch} already has content")
            return
        
        print(f"Creating basic Ubuntu root filesystem for {arch}...")
        print("This may take several minutes...")
        
        try:
            self.run_command([
                "debootstrap", f"--arch={debootstrap_arch}", "jammy", 
                str(rootfs_dir), "http://archive.ubuntu.com/ubuntu/"
            ])
            
            # Set proper ownership
            self.run_command(["chown", "-R", "root:root", str(rootfs_dir)])
            print(f"✓ Basic root filesystem for {arch} created")
            
        except subprocess.CalledProcessError:
            print(f"⚠ Failed to create root filesystem for {arch} with debootstrap")
            print(f"  You'll need to manually populate {rootfs_dir}")

    def configure_firewall(self):
        """Configure firewall rules if UFW is active"""
        print("🔥 Configuring firewall...")
        
        # Check if UFW is active
        try:
            result = self.run_command(["ufw", "status"], capture_output=True, check=False)
            if "Status: active" not in result.stdout:
                print("✓ UFW is not active, skipping firewall configuration")
                return
        except FileNotFoundError:
            print("✓ UFW not installed, skipping firewall configuration")
            return
        
        # UFW rules for PXE services
        rules = [
            ["allow", "69/udp"],      # TFTP
            ["allow", "2049/tcp"],    # NFS
            ["allow", "111/tcp"],     # RPC
            ["allow", "111/udp"],     # RPC
            ["allow", "67/udp"],      # DHCP server
            ["allow", "68/udp"],      # DHCP client
            ["allow", "53/udp"],      # DNS (dnsmasq)
            ["allow", "53/tcp"]       # DNS (dnsmasq)
        ]
        
        for rule in rules:
            try:
                self.run_command(["ufw"] + rule, check=False)
            except subprocess.CalledProcessError:
                pass  # Rule might already exist

    def start_services(self):
        """Start and enable services"""
        print("🔄 Starting and enabling services...")
        
        for service in self.services:
            print(f"Starting {service}...")
            try:
                # Enable service
                self.run_command(["systemctl", "enable", service])
                # Start service
                self.run_command(["systemctl", "start", service])
                print(f"✓ {service} started and enabled")
            except subprocess.CalledProcessError:
                print(f"⚠ Failed to start {service}")
        
        # Export NFS shares
        try:
            self.run_command(["exportfs", "-ra"])
            print("✓ NFS exports refreshed")
        except subprocess.CalledProcessError:
            print("⚠ Failed to refresh NFS exports")

    def verify_setup(self):
        """Verify the setup"""
        print("✅ Verifying setup...")
        
        # Check service status
        for service in self.services:
            try:
                result = self.run_command(["systemctl", "is-active", service], capture_output=True)
                status = result.stdout.strip()
                if status == "active":
                    print(f"✓ {service}: {status}")
                else:
                    print(f"⚠ {service}: {status}")
            except subprocess.CalledProcessError:
                print(f"✗ {service}: failed")
        
        # Check if kernel files exist
        kernel_files = [
            self.wce_boot_dir / "vmlinuz",
            self.wce_boot_dir / "initrd.img"
        ]
        
        missing_files = []
        for file_path in kernel_files:
            if file_path.exists():
                print(f"✓ {file_path} exists")
            else:
                print(f"⚠ {file_path} missing")
                missing_files.append(file_path)
        
        # Summary
        print("\n" + "="*60)
        print("🎉 WCE PXE Server Setup Complete!")
        print("="*60)
        print(f"Server IP: {self.server_ip}")
        print(f"TFTP Directory: {self.netboot_dir}")
        print(f"NFS Root (amd64): {self.wcetriage_amd64_dir}")
        print(f"NFS Root (x32): {self.wcetriage_x32_dir}")
        print(f"Kernel Directory: {self.wce_boot_dir}")
        
        print(f"\n📋 Directory Structure:")
        print(f"├── {self.netboot_dir}/")
        print(f"│   ├── pxelinux.cfg/default")
        print(f"│   ├── wce/")
        print(f"│   ├── wce_amd64/")
        print(f"│   └── wce_x32/")
        print(f"└── {self.netclient_dir}/")
        print(f"    ├── wcetriage_amd64/")
        print(f"    └── wcetriage_x32/")
        
        print(f"\n📋 Next Steps:")
        print("1. Place architecture-specific kernels in:")
        print(f"   - {self.wce_amd64_dir}/vmlinuz and initrd.img")
        print(f"   - {self.wce_x32_dir}/vmlinuz and initrd.img")
        print("2. Configure client machines for PXE boot")
        print("3. Test with a client machine")
        print("4. The dnsmasq configuration handles both DHCP and TFTP")

    def run(self, skip_rootfs: bool = False, architectures: List[str] = None):
        """Run the complete setup"""
        if architectures is None:
            architectures = ["amd64"]
            
        print("🚀 Starting WCE PXE Server Setup")
        print("="*60)
        
        if not self.check_root():
            print("❌ This script must be run as root")
            sys.exit(1)
        
        try:
            self.update_package_list()
            self.install_packages()
            self.create_directories()
            self.configure_tftp()
            self.setup_pxe_files()
            self.copy_kernel_files()
            self.create_pxe_config()
            self.configure_nfs()
            self.configure_dnsmasq()
            
            if not skip_rootfs:
                for arch in architectures:
                    self.setup_basic_rootfs(arch)
            
            self.configure_firewall()
            self.start_services()
            self.verify_setup()
            
        except KeyboardInterrupt:
            print("\n❌ Setup interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            sys.exit(1)


def get_default_ip():
    """Get the default IP address of this machine"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "10.3.2.1"  # WCE default


def get_default_interface():
    """Get the default network interface"""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"], 
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.split('\n'):
            if 'default via' in line:
                parts = line.split()
                if 'dev' in parts:
                    dev_index = parts.index('dev')
                    if dev_index + 1 < len(parts):
                        return parts[dev_index + 1]
    except:
        pass
    return "eth0"


def main():
    parser = argparse.ArgumentParser(description="Setup WCE PXE Boot Server on Ubuntu 24.04 LTS")
    parser.add_argument("--server-ip", default=get_default_ip(), 
                       help="Server IP address (default: auto-detect)")
    parser.add_argument("--interface", default=get_default_interface(),
                       help="Network interface for DHCP (default: auto-detect)")
    parser.add_argument("--dhcp-range", default="10.3.2.100-10.3.2.200",
                       help="DHCP IP range (default: 10.3.2.100-10.3.2.200)")
    parser.add_argument("--gateway", default="10.3.2.1",
                       help="Gateway IP address (default: 10.3.2.1)")
    parser.add_argument("--skip-rootfs", action="store_true",
                       help="Skip creating basic root filesystem")
    parser.add_argument("--architectures", nargs="+", default=["amd64"],
                       choices=["amd64", "x32", "i386"],
                       help="Architectures to set up (default: amd64)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show configuration but don't make changes")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - Configuration Preview:")
        print(f"Server IP: {args.server_ip}")
        print(f"Network Interface: {args.interface}")
        print(f"DHCP Range: {args.dhcp_range}")
        print(f"Gateway: {args.gateway}")
        print(f"Architectures: {args.architectures}")
        print(f"Skip rootfs: {args.skip_rootfs}")
        return
    
    setup = PXEServerSetup(
        server_ip=args.server_ip,
        network_interface=args.interface,
        dhcp_range=args.dhcp_range,
        gateway=args.gateway
    )
    
    setup.run(skip_rootfs=args.skip_rootfs, architectures=args.architectures)


if __name__ == "__main__":
    main()
    
