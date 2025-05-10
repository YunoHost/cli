# YunoHost CLI

This project aims to replace the current `yunohost` command line whose source
code is tightly coupled to the server.

It uses the YunoHost REST API, and can be use either locally (hostname == localhost)
or remotely.

The command line format is extracted from the `actionsmap.yml` that it can either
find locally installed by the yunohost server, or fallback on its local copy.

It saves its configuration at `~/.config/yunohost/cli.toml`.
