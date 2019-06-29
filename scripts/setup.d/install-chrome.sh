#
#
# Add Google signing key
#
wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

# Using add-apt-repository using google's source list result in error as it exports both i386 and amd64 but 18.04 doesn't support i386 and complains.
#
echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list

#
sudo apt update
#
# Install Google Chrome
#
sudo apt install -y --no-install-recommends google-chrome-stable
#
