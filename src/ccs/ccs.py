import sys
import time
import json

import httpx2
from loguru import logger
import click
from dotenv import load_dotenv

CCS_VERSION = "1.0.0"
CCS_FULL_NAME = "Crafty Controller Starter"

class CCException(BaseException):
    pass

class CCNotAuthorized(CCException):
    exc_message: str = "User is not authorized (wrong token) or does not have permissions to do this action"


class CraftyClient:
    def __init__(self, crafty_base_url, ignore_ssl: bool, api_key: str, *, timeout_seconds: float = 30.0, retries: int = 10):
        self.crafty_base_url = httpx2.URL(crafty_base_url).join("api/v2/")
        self.client = httpx2.Client(headers={"Authorization": f"Bearer {api_key}"}, base_url=self.crafty_base_url, timeout=httpx2.Timeout(timeout=timeout_seconds),
                                   transport=httpx2.HTTPTransport(retries=retries, verify=not ignore_ssl))
    
    def request(self, url, method="GET", data=None, params: dict | None = None):
        if params:
            url = self.client.base_url.join(url).copy_merge_params(params=params)
        if data is not None and method != "POST":
            raise ValueError("CraftyClient does not support data with not POST method")
        elif data is not None and method == "POST":
            raw_resp = self.client.post(url=url, data=data)
        else:
            raw_resp = self.client.request(method=method, url=url)
        logger.trace(f"{raw_resp.request.url} {raw_resp.status_code}")
        logger.trace(raw_resp.text)
        if raw_resp.status_code in (401, 403):
            raise CCNotAuthorized()
        resp = raw_resp.json()
        return resp
    
    def get_server_api(self, server_id: str):
        return CraftyServer(self, server_id)
    
    def list_servers(self):
        resp = self.request("servers")
        return resp["data"]

class CraftyServer:
    def __init__(self, cc: CraftyClient, server_id: str):
        self.client = cc
        self.server_id = server_id
        self.base_url = self.client.crafty_base_url.join(f"servers/{server_id}/")
    
    def _request(self, url, method="GET", data=None, params: dict | None = None):
        resp = self.client.request(self.base_url.join(url), method, data=data, params=params)
        return resp
    
    def stats(self):
        resp = self._request("stats")
        return resp["data"]
    
    def is_running(self):
        return self.stats()["running"]
    
    def get_online_count(self):
        return self.stats()["online"]
    
    def get_players(self):
        return json.loads(self.stats()["players"])
    
    def history(self):
        resp = self._request("history")
        return resp["data"]
    
    def start(self):
        resp = self._request("action/start_server", method="POST")
        return resp
    
    def stop(self):
        resp = self._request("action/stop_server", method="POST")
        return resp
    
    def kill(self):
        resp = self._request("action/kill_server", method="POST")
        return resp
    
    def restart(self):
        resp = self._request("action/restart_server", method="POST")
        return resp
    
    def send_stdin(self, command: str):
        resp = self._request("stdin", method="POST", data=command)
        return resp
    
    def get_stdout(self, file: bool = False, raw: bool = True):
        resp = self._request("logs", "GET", params=dict(file=file, raw=raw))
        return resp

DOTENV_LOADED = False

@click.group()
@click.option("--dotenv", "dotenv_path", type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True), default=None, help=".env file to load variables from there")
@click.option("--crafty-base-url", default="https://127.0.0.1:8443", type=str, help="URL to Crafty Controller instance", envvar="CCS_BASE_URL")
@click.option("--dont-ignore-ssl", default=False, is_flag=True, flag_value=True, help="Use this only if your Crafty instance is behind reverse proxy with proper ssl setup", envvar="CCS_DONT_IGNORE_SSL")
# @click.option("--api-key", required=True, help="API Key that can start and stop needed servers", envvar="CCS_API_KEY")
# XXX: Disabled required option as workaround
@click.option("--api-key", required=False, help="API Key that can start and stop needed servers", envvar="CCS_API_KEY")
@click.option("--console-log", default=False, is_flag=True, flag_value=True, help="Turn on logging in console output. You can also use loguru env vars to customize it. Disabled by default", envvar="CCS_CONSOLE_LOG")
@click.option("--file-log", default=False, is_flag=True, flag_value=True, help="Turn on logging into file ccs.log in same folder", envvar="CCS_FILE_LOG")
@click.option("--timeout", default=60, type=click.IntRange(min=10, max=120), help="Maximum timeout for HTTP client (in seconds)")
@click.option("--retries", default=10, type=click.IntRange(min=0, max=20), help="Retries for HTTP client")
@click.version_option(version=CCS_VERSION, prog_name=CCS_FULL_NAME)
@click.pass_context
def cli(ctx, dotenv_path: str, crafty_base_url: str, dont_ignore_ssl: bool, api_key: str, console_log: bool, file_log: bool, timeout: int, retries: int):
    """Small cli to manage minecraft servers managed with Crafty Controller.
    Source: https://github.com/NoPlagiarism/ccs"""
    global DOTENV_LOADED
    if file_log:
        logger.add("ccs.log", rotation="24h", level="TRACE")
    if not console_log:
        logger.remove()
    elif DOTENV_LOADED:
        # Readd logger
        logger.add(sys.stderr)
    if dotenv_path and not DOTENV_LOADED:
        logger.debug(f"Loading .env file ({dotenv_path})")
        load_dotenv(dotenv_path)
        DOTENV_LOADED = True
        cli()
    if api_key is None:
        raise click.BadOptionUsage("--api-key", message="--api-key option is missing", ctx=ctx)
    ctx.ensure_object(dict)
    ctx.obj["client"] = CraftyClient(crafty_base_url=crafty_base_url, ignore_ssl=not dont_ignore_ssl, api_key=api_key, timeout_seconds=timeout, retries=retries)

@cli.command("ls")
@click.option("--json", 'json_output', default=False, is_flag=True, flag_value=True, help="Output data in json")
@click.pass_context
def list_servers(ctx, json_output: bool):
    """Get list of servers with their names and UUIDs"""
    client: CraftyClient = ctx.obj["client"]
    servers = client.list_servers()
    if not servers and not json_output:
        click.echo("No servers available :(")
    elif not servers and json_output:
        click.echo("[]")
    else:
        if json_output:
            res = json.dumps(servers, ensure_ascii=False, indent=2)
            click.echo(res)
            return
        for x in servers:
            click.echo(f"{x['server_name']}: {x['server_id']}")


@cli.group("server")
@click.option("--server-id", type=click.UUID, required=True, help="Server ID", envvar="CCS_SERVER")
@click.pass_context
def server_group(ctx, server_id):
    "Manage server"
    client: CraftyClient = ctx.obj["client"]
    server = client.get_server_api(server_id)
    ctx.obj["server"] = server


@server_group.command("start")
@click.option("--sleep", type=click.IntRange(min=0, max=40), help="Workaround for lazymc to show that server is loading", default=0)
@click.pass_context 
def server_start(ctx, sleep: None | int):
    "Starts server"
    server: CraftyServer = ctx.obj["server"]
    server.start()
    if sleep:
        logger.debug(f"Sleeping for {sleep} seconds")
        time.sleep(sleep)

@server_group.command("restart")
@click.option("--sleep", type=click.IntRange(min=0, max=40), help="Workaround for lazymc to show that server is loading", default=0)
@click.pass_context 
def server_restart(ctx, sleep: None | int):
    "Restarts server"
    server: CraftyServer = ctx.obj["server"]
    server.restart()
    if sleep: 
        logger.debug(f"Sleeping for {sleep} seconds")
        time.sleep(sleep)

@server_group.command("stop")
@click.pass_context 
def server_stop(ctx):
    "Stops server"
    server: CraftyServer = ctx.obj["server"]
    server.stop()

@server_group.command("kill")
@click.pass_context 
def server_kill(ctx):
    "Forcefully kills server"
    server: CraftyServer = ctx.obj["server"]
    server.kill()

@server_group.command("stats")
@click.pass_context 
def server_stats(ctx):
    "Stats of the server in json format"
    server: CraftyServer = ctx.obj["server"]
    stats = server.stats()
    res = json.dumps(stats, ensure_ascii=False, indent=2)
    click.echo(res)

@server_group.command("history")
@click.option("--last", "last", type=click.IntRange(min=0), default=0, help="How many last history data to display. Default: 0 (Display all of them)")
@click.pass_context 
def server_history(ctx, last: int):
    "Stats of the server in json format for last hour (hardcoded timedelta in Crafty)"
    server: CraftyServer = ctx.obj["server"]
    history = server.history()
    history = history[-last:]
    res = json.dumps(history, ensure_ascii=False, indent=2)
    click.echo(res)

@server_group.command("stdin")
@click.argument("command", type=str, nargs=-1)
@click.pass_context
def server_send_stdin(ctx, command: str):
    "Send command to stdin of console"
    command = " ".join(command)
    server: CraftyServer = ctx.obj["server"]
    raw_res = server.send_stdin(command)
    res = json.dumps(raw_res, ensure_ascii=False, indent=2)
    click.echo(res)

@server_group.command("stdout")
@click.option("--file", "file", default=False, is_flag=True, flag_value=True, help="Whether to read the log file or stdout. Defaults to false (standard out)")
@click.option("--last", "last_lines", type=click.IntRange(min=0), default=0, help="How many last lines to display. Default: 0 (Disabled)")
@click.option("--json", 'json_output', default=False, is_flag=True, flag_value=True, help="Output data in json")
@click.option("--no-pager", "--no-p", "disable_pager", default=False, is_flag=True, flag_value=True, help="Disables pager by Click and print all lines")
@click.pass_context
def server_get_stdout(ctx, file: bool, last_lines: int, json_output: bool, disable_pager: bool):
    "Get stdout of server"
    server: CraftyServer = ctx.obj["server"]
    raw_res = server.get_stdout(file=file)
    if last_lines != 0:
        raw_res["data"] = raw_res["data"][-last_lines:]
    if json_output:
        res = json.dumps(raw_res["data"], ensure_ascii=False, indent=2)
        click.echo(res)
    else:
        res = "\n".join(raw_res["data"])
        if not disable_pager:
            click.echo_via_pager(res)
        else:
            click.echo(res)


@logger.catch(reraise=True)
def main():
    try:
        cli()
    except CCNotAuthorized:
        click.echo(CCNotAuthorized.exc_message)


if __name__ == "__main__":
    main()
