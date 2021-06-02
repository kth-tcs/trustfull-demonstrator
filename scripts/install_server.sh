#!/bin/bash
set -e
set -x

sudo apt-get update -q
sudo apt-get full-upgrade -y
sudo apt-get install -y \
    tmux vim wget zip \
    build-essential m4 cpp gcc make libtool automake autoconf libgmp-dev openjdk-11-jdk

# Workaround for SSL issue https://askubuntu.com/a/1233456
cat << EOF > ~/ssl.conf
openssl_conf = default_conf

[ default_conf ]

ssl_conf = ssl_sect

[ssl_sect]

system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1.2
CipherString = DEFAULT:@SECLEVEL=1
EOF

# https://www.verificatum.org/html/install_vmn.html#ubuntu_18.04.4
# Fetch, build, and install VMN as a single demonstration package.
OPENSSL_CONF="$HOME/ssl.conf" wget https://www.verificatum.org/files/verificatum-vmn-3.0.4-full.tar.gz
tar xvfz verificatum-vmn-3.0.4-full.tar.gz
rm verificatum*.tar.gz
cd verificatum-vmn-3.0.4-full
make install

echo 'done!'
sudo reboot
