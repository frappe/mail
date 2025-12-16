#!/bin/bash
set -e

# Configuration variables
ANSIBLE_VENV_PATH="/opt/ansible-venv"
PYTHON_VERSION="3.11.9"

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
        # Detect Ubuntu 24.04 and use pyenv + Python 3.11 for compatibility
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            if [ "$ID" = "ubuntu" ] && [ "$VERSION_ID" = "24.04" ]; then
                echo "Ubuntu 24.04 detected, installing pyenv + Python ${PYTHON_VERSION} + Ansible"
                
                # Install dependencies for pyenv and Python compilation
                sudo apt-get update
                sudo apt-get install -y build-essential libssl-dev zlib1g-dev \
                    libbz2-dev libreadline-dev libsqlite3-dev curl git \
                    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
                    libffi-dev liblzma-dev
                
                # Install pyenv if not already installed
                if [ ! -d "$HOME/.pyenv" ]; then
                    curl https://pyenv.run | bash
                    
                    # Add pyenv to PATH
                    export PYENV_ROOT="$HOME/.pyenv"
                    export PATH="$PYENV_ROOT/bin:$PATH"
                    eval "$(pyenv init -)"
                    
                    # Add to shell profile for persistence
                    cat >> ~/.bashrc << 'PYENV_EOF'

# Pyenv configuration
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
PYENV_EOF
                else
                    export PYENV_ROOT="$HOME/.pyenv"
                    export PATH="$PYENV_ROOT/bin:$PATH"
                    eval "$(pyenv init -)"
                fi
                
                # Install Python version
                if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
                    echo "Installing Python ${PYTHON_VERSION}..."
                    pyenv install $PYTHON_VERSION
                fi
                
                # Create virtualenv for Ansible
                if [ ! -d "$ANSIBLE_VENV_PATH" ]; then
                    echo "Creating Ansible virtualenv..."
                    pyenv virtualenv $PYTHON_VERSION ansible-venv
                    # Move to configured path and create symlink
                    sudo mv "$HOME/.pyenv/versions/ansible-venv" "$ANSIBLE_VENV_PATH"
                    sudo ln -sf "$ANSIBLE_VENV_PATH" "$HOME/.pyenv/versions/ansible-venv"
                else
                    echo "Ansible virtualenv already exists at ${ANSIBLE_VENV_PATH}"
                fi
                
                # Install Ansible using the virtualenv's pip directly
                echo "Installing Ansible..."
                sudo "${ANSIBLE_VENV_PATH}/bin/pip" install --upgrade pip
                sudo "${ANSIBLE_VENV_PATH}/bin/pip" install ansible
                
                # Create symlink for global ansible access
                sudo ln -sf "${ANSIBLE_VENV_PATH}/bin/ansible" /usr/local/bin/ansible || true
                sudo ln -sf "${ANSIBLE_VENV_PATH}/bin/ansible-playbook" /usr/local/bin/ansible-playbook || true
                
                echo "Ansible installation complete with Python ${PYTHON_VERSION}"
                ansible --version
            else
                # Standard Debian/Ubuntu installation for other versions
                sudo apt-get update
                sudo apt-get install -y software-properties-common python3 python3-apt python3-pip
                sudo apt-get install -y ansible || echo "Fallback to pip"
            fi
        else
            # Fallback to standard installation
            sudo apt-get update
            sudo apt-get install -y software-properties-common python3 python3-apt python3-pip
            sudo apt-get install -y ansible || echo "Fallback to pip"
        fi
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
