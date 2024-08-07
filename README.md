# django-ixp-tracker

[![PyPI](https://img.shields.io/pypi/v/django-ixp-tracker.svg)](https://pypi.org/project/django-ixp-tracker/)
[![Tests](https://github.com/InternetSociety/django-ixp-tracker/actions/workflows/test.yml/badge.svg)](https://github.com/InternetSociety/django-ixp-tracker/actions/workflows/test.yml)
[![Changelog](https://img.shields.io/github/v/release/InternetSociety/django-ixp-tracker?include_prereleases&label=changelog)](https://github.com/InternetSociety/django-ixp-tracker/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/InternetSociety/django-ixp-tracker/blob/main/LICENSE)

Library to retrieve and manipulate data about IXPs

## Installation

Install this library using `pip`:
```bash
pip install django-ixp-tracker
```
## Usage

1. Add to your INSTALLED_APPS setting like this:

   INSTALLED_APPS = [
   ...,
   "ixp_tracker",
   ]

    Note: this app has no web-facing components so you don't need to add anything to `urls.py` etc

2. Run ``python manage.py migrate`` to create the models.
3. Add the relevant settings to your config. `IXP_TRACKER_PEERING_DB_URL` will use a default if you don't provide a value so you probably don't need that. But you will need to set `IXP_TRACKER_PEERING_DB_KEY` to authenticate against the API.
4. Ensure you have code to look up the registration country for an ASN. You should implement the Protocol `ixp_tracker.importers.ASNGeoLookup`

## Development

To contribute to this library, first checkout the code. Then create a new virtual environment:
```bash
cd django-ixp-tracker
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
pytest
```
We use [pre-commit](https://pre-commit.com/) for linting etc on push. Run:
```bash
pre-commit install
```
from the repo top-level dir to set it up.

## Peering Db libraries

PeeringDb provide their own [vanilla Python](https://github.com/peeringdb/peeringdb-py) and [Django](https://github.com/peeringdb/django-peeringdb) libs, but we have decided not to use these.

Both libs are designed to keep a local copy of the current data and to keep that copy in sync with the central copy via the API.

As we need to keep a historical record (e.g. for IXP growth stats over time), we would have to provide some sort of wrapper over those libs anyway.

In addition to that, the [historical archives of PeeringDb data](https://publicdata.caida.org/datasets/peeringdb/) use flat lists of the different object types in json. We can retrieve the data from the API in the same way so it makes it simpler to implement.
