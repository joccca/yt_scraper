import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname), encoding="utf8").read()


setup(
    name="yt_scraper",
    version="1.0",
    python_requires=">=3.7",
    description="Looks at YouTube search results – by netzpolitik.org, 2023",
    long_description=read("README.md"),
    author="jocca",
    author_email="jocca@netzpolitik.org",
    url="https://github.com/joccca/yt_scraper",
    packages=["yt_scraper"],
    install_requires=["requests", "pyppeteer"],
)
