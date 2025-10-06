#!/bin/bash
set -e

if [ -f /etc/debian_version ]; then
    distro=debian
elif [ -f /etc/redhat-release ]; then
    distro=rhel
elif [ -f /etc/arch-release ]; then
    distro=arch
else
    distro=unknown
fi

echo "Detected distro: $distro"

case "$distro" in
    debian)
        sudo apt-get update
        sudo apt-get install -y software-properties-common python3 python3-apt python3-pip
        sudo apt-get install -y ansible || echo "Fallback to pip"
        ;;
    rhel)
        sudo yum install -y epel-release python3 python3-pip || sudo dnf install -y python3 python3-pip
        sudo yum install -y ansible || sudo dnf install -y ansible || echo "Fallback to pip"
        ;;
    arch)
        sudo pacman -Sy --noconfirm python python-pip ansible
        ;;
    *)
        echo "Unknown distro, will try pip install"
        ;;
esac

if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 not found, installing..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3
fi

if ! command -v ansible >/dev/null 2>&1; then
    echo "Installing Ansible via pip"
    python3 -m pip install --user ansible
fi

echo "Ansible installation complete"
