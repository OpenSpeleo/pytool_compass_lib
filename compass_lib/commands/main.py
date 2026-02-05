from __future__ import annotations

import argparse
from importlib.metadata import entry_points

import compass_lib


def main():
    registered_commands = entry_points(group="compass_lib.actions")

    parser = argparse.ArgumentParser(prog="compass_lib")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s version: {compass_lib.__version__}",
    )
    parser.add_argument(
        "command",
        choices=registered_commands.names,
    )
    parser.add_argument(
        "args",
        help=argparse.SUPPRESS,
        nargs=argparse.REMAINDER,
    )

    args = argparse.Namespace()
    parser.parse_args(namespace=args)

    main_fn = registered_commands[args.command].load()
    return main_fn(args.args)
