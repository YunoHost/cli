# YunoHost CLI

This project aims to replace the current `yunohost` command line whose source
code is tightly coupled to the server.

It uses the YunoHost REST API, and can be use either locally (hostname == localhost)
or remotely.

The command line format is extracted from the `actionsmap.yml` that it can either
find locally installed by the yunohost server, or fallback on its local copy.

It saves its configuration at `~/.config/yunohost/cli.toml`.

## Installation

This tool is not yet published, on Pypi nor debian repos.

## Usage

It is for now installed as `yunohost-cli` and `ynh` to prevent conflicts with the
existing `yunohost` command line.

```
uv run ynh --help

# Login and save the creds
uv run cli auth myserver.tld myusername mypassword

uv run ynh user list
```
