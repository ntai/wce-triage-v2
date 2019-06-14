import setuptools

with open("README.md", "r") as fh:
  long_description = fh.read()

setuptools.setup(
  name="wce_triage",
  version="0.1.0",
  author="Naoyuki Tai",
  author_email="ntai@cleanwinner.com",
  description="WCE Triage",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/ntai/wce-triage-v2",
  packages=setuptools.find_packages(),
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
  ],
)
