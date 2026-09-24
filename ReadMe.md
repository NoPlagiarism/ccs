# CraftyContollerStarter

Simple cli program to control MC servers using [Crafty Controller](https://craftycontrol.com) API

## Usage

To list servers and their ids

```bash
ccs.py --api-key KEY ls
```

To start a server

```bash
ccs.py --api-key KEY server --server-id SERVER_UUID start
```

To start a server using variables from `.env` file

```bash
ccs.py --dotenv .env server start
```

To get a list of online players with help of [jq](https://jqlang.org)

```bash
ccs.py --dotenv .env server stats | jq '.players | gsub("\u0027"; "\"") | fromjson'
```

## Environment Variables

You can state them in system or using `.env` file

- `CCS_BASE_URL`
  - Base url of Crafty instance. Defaults to `https://127.0.0.1:8443` a.k localhost on default port
- `CCS_API_KEY`
  - API key to authorize with access to needed servers
- `CCS_CONSOLE_LOG`
  - Turn on logging in console output. You can also use loguru env vars to customize it. Defaults to `False`
- `CCS_FILE_LOG`
  - Turn on logging into file ccs.log in same folder.  Defaults to `False`
- `CCS_SERVER`
  - Default server id to tamper with
- `CCS_DONT_IGNORE_SSL`
  - Defaults to `False`. Don't touch if you don't understand it


## lazymc

Here's an small part of my config for [lazymc](https://github.com/timvisee/lazymc) that I use with CCS

```toml
[server]
address = "127.0.0.1:3229"
directory = "."
# or ccs.exe for standalone executable
# --sleep {approximate time for server start}
command = "uv run ccs.py --file-log --api-key \"eyJhbG...\" server --server-id 3c8b2750-064d-4745-b1bd-e7a006df7149 start --sleep 28"

[join]
# Other methods were not tested
methods = [
    "kick",
]
```

## Building

- Windows builds are creating using nuitka
  - ```
    uv run nuitka .\ccs.py --mode=onefile
    ```
- Python scripts are generated with [pep723fy](https://github.com/ninoseki/pep723fy)
