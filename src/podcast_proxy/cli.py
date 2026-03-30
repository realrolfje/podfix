from __future__ import annotations

import argparse
import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path

from .config import load_config
from .service import sync


def main() -> None:
    parser = argparse.ArgumentParser(prog="podcast-proxy")
    parser.add_argument("--log-level", default="INFO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--config", required=True)

    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.add_argument("--config", required=True)

    rebuild_images_parser = subparsers.add_parser("rebuild-images")
    rebuild_images_parser.add_argument("--config", required=True)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--config", required=True)
    serve_parser.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )

    if args.command == "sync":
        config = load_config(args.config)
        index_path = sync(config, rebuild=False)
        print(index_path)
        return

    if args.command == "rebuild":
        config = load_config(args.config)
        index_path = sync(config, rebuild=True)
        print(index_path)
        return

    if args.command == "rebuild-images":
        config = load_config(args.config)
        index_path = sync(config, rebuild_images=True)
        print(index_path)
        return

    if args.command == "serve":
        config = load_config(args.config)
        serve(config.public_dir, args.port)


def serve(directory: Path, port: int) -> None:
    handler = partial_handler(directory)
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as server:
        print(f"Serving {directory} on http://0.0.0.0:{port}")
        server.serve_forever()


def partial_handler(directory: Path) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=os.fspath(directory), **kwargs)

    return Handler


if __name__ == "__main__":
    main()
