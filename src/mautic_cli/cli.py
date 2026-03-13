from __future__ import annotations

import sys

import click
import httpx

from mautic_cli import __version__
from mautic_cli.auth import resolve_credentials
from mautic_cli.client import MauticClient, MauticApiError
from mautic_cli.config import ConfigManager
from mautic_cli.context import MauticContext
from mautic_cli.output import get_err_console

# Commands that don't need API credentials
_NO_AUTH_COMMANDS = {"auth", "version", "completion", None}


def is_tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_BANNER = r"""
                          __  _              ___
   ____ ___  ____ ___  __/ /_(_)____   _____/ (_)
  / __ `__ \/ __ `/ / / / __/ / ___/  / ___/ / /
 / / / / / / /_/ / /_/ / /_/ / /__   / /__/ / /
/_/ /_/ /_/\__,_/\__,_/\__/_/\___/   \___/_/_/
"""


class MauticCLI(click.Group):
    """Click group with top-level error handling and custom help."""

    def format_help(self, ctx, formatter):
        from mautic_cli.output import get_console
        con = get_console()
        con.print(f"[mautic]{_BANNER}[/mautic]", highlight=False)
        con.print(f"  [dim]Control Mautic from the command line or any AI coding agent.[/dim]")
        con.print(f"  [dim]Built for humans and AI agents - v{__version__}[/dim]\n")

        # Render usage + options + commands without the docstring
        self.format_usage(ctx, formatter)
        self.format_options(ctx, formatter)
        self.format_epilog(ctx, formatter)

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except httpx.ConnectError as e:
            err = get_err_console()
            msg = str(e)
            if "CERTIFICATE_VERIFY_FAILED" in msg:
                err.print("[error]Error:[/error] SSL certificate verification failed. Use [bold]--no-verify-ssl[/bold] for self-signed certs.")
            else:
                err.print(f"[error]Error:[/error] Could not connect to Mautic instance. {msg}")
            ctx.exit(1)
        except httpx.TimeoutException:
            get_err_console().print("[error]Error:[/error] Request timed out. Check that the Mautic instance is reachable.")
            ctx.exit(1)
        except MauticApiError as e:
            get_err_console().print(f"[error]Error:[/error] {e.message} [dim](HTTP {e.code})[/dim]")
            ctx.exit(1)


@click.group(cls=MauticCLI, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="mautic-cli")
@click.option("--format", "fmt", type=click.Choice(["json", "table", "csv"]), default="json", help="Output format.")
@click.option("--pretty", is_flag=True, default=False, help="Pretty-print JSON.")
@click.option("--page-all", is_flag=True, default=False, help="Auto-paginate, output NDJSON per record.")
@click.option("--dry-run", is_flag=True, default=False, help="Show HTTP request without executing.")
@click.option("--verbose", is_flag=True, default=False, help="Show HTTP details.")
@click.option("--published-only", is_flag=True, default=False, help="Filter to published items only.")
@click.option("--no-verify-ssl", is_flag=True, default=False, help="Skip SSL certificate verification.")
@click.option("--profile", default="default", help="Named profile from config.")
@click.pass_context
def cli(ctx, fmt, pretty, page_all, dry_run, verbose, published_only, no_verify_ssl, profile):
    """\b"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return

    mctx = MauticContext()
    mctx.fmt = fmt
    mctx.pretty = pretty if pretty else is_tty()
    mctx.dry_run = dry_run
    mctx.page_all = page_all
    mctx.published_only = published_only
    mctx.verify_ssl = not no_verify_ssl
    ctx.obj = mctx

    # Skip auth entirely when showing help
    if "--help" in sys.argv:
        return

    # Commands that don't require auth can still use it if available
    needs_auth = ctx.invoked_subcommand not in _NO_AUTH_COMMANDS

    try:
        config = ConfigManager()
        creds = resolve_credentials(config=config, profile=profile)
        # Config can also disable SSL verification
        if mctx.verify_ssl and creds.get("verify_ssl") is False:
            mctx.verify_ssl = False
        mctx.client = MauticClient(creds, dry_run=dry_run, verbose=verbose, verify_ssl=mctx.verify_ssl)
    except ValueError as e:
        if needs_auth:
            get_err_console().print(f"[error]Error:[/error] {e}")
            ctx.exit(1)


@cli.command("version")
@click.pass_context
def version_cmd(ctx):
    """Show CLI and Mautic instance version."""
    import json

    mctx = ctx.obj
    info = {"cli_version": __version__}
    if mctx and mctx.client:
        try:
            ver = mctx.client.detect_version()
            info["mautic_version"] = ".".join(str(x) for x in ver)
            info["api_v2_available"] = ver >= (7, 0, 0)
        except Exception:
            info["mautic_version"] = "unknown"
            info["api_v2_available"] = False
    click.echo(json.dumps(info, indent=2))


@cli.command()
@click.argument("shell", required=False, type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell):
    """Set up shell tab-completion for mautic commands."""
    import os
    import subprocess

    if not shell:
        user_shell = os.environ.get("SHELL", "")
        if "zsh" in user_shell:
            shell = "zsh"
        elif "fish" in user_shell:
            shell = "fish"
        else:
            shell = "bash"

    env = {**os.environ, "_MAUTIC_COMPLETE": f"{shell}_source"}
    result = subprocess.run(
        ["mautic"],
        env=env,
        capture_output=True,
        text=True,
    )

    if is_tty():
        from mautic_cli.output import get_console
        con = get_console()

        if shell == "zsh":
            rc_file = "~/.zshrc"
        elif shell == "fish":
            rc_file = "~/.config/fish/completions/mautic.fish"
        else:
            rc_file = "~/.bashrc"

        con.print(f"\n[mautic]Tab-completion for mautic[/mautic] [dim]({shell})[/dim]\n")
        if shell == "fish":
            con.print(f"  mautic completion fish > {rc_file}\n")
        else:
            con.print(f"  echo '\\neval \"$(mautic completion {shell})\"' >> {rc_file}")
            con.print(f"  source {rc_file}\n")
    else:
        click.echo(result.stdout, nl=False)


# Register command groups (lazy imports inside function, no circular dependency)
from mautic_cli.commands import register_commands

register_commands(cli)
