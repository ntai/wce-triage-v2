import setuptools, sys

with open("README.md", "r") as fh:
  long_description = fh.read()

# The wce triage is designed to work with Ubuntu 18.04LTS and after
# that comes with Python 3.6. 
python_version = sys.version_info
need_python_version = (3, 6)

if python_version < need_python_version:
  raise RuntimeError("wce_triage requires Python version %d.%d or higher"
                     % need_python_version)

setuptools.setup(
  name="wce_triage",
  version="0.1.9",
  author="Naoyuki Tai",
  author_email="ntai@cleanwinner.com",
  description="WCE Triage",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/ntai/wce-triage-v2",
  packages=['wce_triage.bin', 'wce_triage.components', 'wce_triage.lib', 'wce_triage.http', 'wce_triage.ops'],
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
  ],
)

