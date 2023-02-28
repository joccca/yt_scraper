# yt_scraper – Looking at YouTube search results

by netzpolitik.org, (c) 2023, GPLv3

This script uses the headless browser pyppeteer to collect YouTube search results for a set of search query and counts the results by its source (channel/creator).
It's a quick and dirty draft that does it's job. Feedback and PRs are welcome.

## Install

### 0. Dependencies

- git
- [python](https://www.python.org/downloads) > 3.7
- [pip](https://pip.pypa.io/en/stable/installing)
- [setuptools](https://pypi.python.org/pypi/setuptools)
- [virtualenv](https://virtualenv.pypa.io/en/latest/installation) (development)

```
$ pip install virtualenv setuptools
```

### 1. Clone Repository

```
$ git clone https://github.com/joccca/yt_scraper
$ cd yt_scraper
```

### 2. Install Dependencies

```
$ virtualenv venv
$ . venv/bin/activate  # Windows: `source ./venv/Scripts/activate`
$ pip install --editable .
```

- `deactivate` to exit virtualenv

## Usage

- edit script: set search queries etc.
- run in venv: `python yt_scraper.py`
- a browser opens if there is a CAPTCHA or GDPR consent page to resolve: resolve and hit ENTER in terminal
- outputs several csv files with results and analysis

### Known Issues

- pyppeteer sometimes crashes: just restart.

## Update

```
$ git pull
$ pip install --editable .
```
