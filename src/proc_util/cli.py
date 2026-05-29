from __future__ import annotations

import argparse
from dataclasses import replace
import json
import multiprocessing
import sys

from .config import Config, default_config_path, load_config, write_default_config
from .runner import RunOptions, run_monitor
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            path = write_default_config(args.config, force=args.force)
            print(path)
            return 0

        if args.command == "show-config":
            config = load_config(args.config)
            print(json.dumps(config.__dict__, ensure_ascii=False, indent=2))
            return 0

        if args.command == "run":
            config = _apply_run_overrides(load_config(args.config), args)
            options = RunOptions(
                once=args.once,
                dry_run=args.dry_run,
                max_iterations=args.max_iterations,
            )
            run_monitor(config, options)
            return 0

        if args.command == "serve":
            config = load_config(args.config)
            if args.output_dir is not None:
                config = replace(config, output_dir=args.output_dir)
                config.validate()
            serve(config, args.host, args.port)
            return 0

        if args.command == "start":
            config = _apply_start_overrides(load_config(args.config), args)
            options = RunOptions(dry_run=args.dry_run)
            process = multiprocessing.get_context("spawn").Process(
                target=run_monitor,
                args=(config, options),
            )
            process.start()
            try:
                serve(config, args.host, args.port)
            finally:
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
            return 0

        parser.print_help()
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proctolog",
        description="Periodically send screenshots to RouterAI Chat Completions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="write a default config file")
    init.add_argument("--config", help=f"default: {default_config_path()}")
    init.add_argument("--force", action="store_true", help="overwrite an existing config")

    show_config = subparsers.add_parser("show-config", help="print resolved config")
    show_config.add_argument("--config", help=f"default: {default_config_path()}")

    run = subparsers.add_parser("run", help="start screenshot monitoring")
    run.add_argument("--config", help=f"default: {default_config_path()}")
    run.add_argument("--once", action="store_true", help="run one screenshot/API cycle")
    run.add_argument("--dry-run", action="store_true", help="capture and log without API calls")
    run.add_argument("--interval", type=float, help="override interval_seconds")
    run.add_argument("--prompt", help="override the configured prompt")
    run.add_argument("--model", help="override the configured model")
    run.add_argument("--detail", choices=["auto", "low", "high"], help="image detail")
    run.add_argument("--output-dir", help="override output_dir")
    run.add_argument(
        "--screenshot-command",
        nargs="+",
        help="override screenshot_command; use {output} as the target path",
    )
    run.add_argument("--max-iterations", type=int, help="stop after N iterations")

    serve_parser = subparsers.add_parser("serve", help="serve transcript over HTTP")
    serve_parser.add_argument("--config", help=f"default: {default_config_path()}")
    serve_parser.add_argument("--output-dir", help="override output_dir")
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="host to bind; 0.0.0.0 makes it visible on the local network",
    )
    serve_parser.add_argument("--port", type=int, default=8765, help="port to bind")

    start = subparsers.add_parser("start", help="run monitor and HTTP server together")
    start.add_argument("--config", help=f"default: {default_config_path()}")
    start.add_argument("--dry-run", action="store_true", help="capture and log without API calls")
    start.add_argument("--interval", type=float, help="override interval_seconds")
    start.add_argument("--prompt", help="override the configured prompt")
    start.add_argument("--model", help="override the configured model")
    start.add_argument("--detail", choices=["auto", "low", "high"], help="image detail")
    start.add_argument("--output-dir", help="override output_dir")
    start.add_argument(
        "--screenshot-command",
        nargs="+",
        help="override screenshot_command; use {output} as the target path",
    )
    start.add_argument(
        "--host",
        default="0.0.0.0",
        help="host to bind; 0.0.0.0 makes it visible on the local network",
    )
    start.add_argument("--port", type=int, default=8765, help="port to bind")
    return parser


def _apply_run_overrides(config: Config, args: argparse.Namespace) -> Config:
    changes = {}
    if args.interval is not None:
        changes["interval_seconds"] = args.interval
    if args.prompt is not None:
        changes["prompt"] = args.prompt
    if args.model is not None:
        changes["model"] = args.model
    if args.detail is not None:
        changes["detail"] = args.detail
    if args.output_dir is not None:
        changes["output_dir"] = args.output_dir
    if args.screenshot_command is not None:
        changes["screenshot_command"] = args.screenshot_command

    updated = replace(config, **changes)
    updated.validate()
    return updated


def _apply_start_overrides(config: Config, args: argparse.Namespace) -> Config:
    return _apply_run_overrides(config, args)


if __name__ == "__main__":
    raise SystemExit(main())
