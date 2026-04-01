from __future__ import annotations

import argparse
import base64
import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import secrets

from .config import load_config
from .service import sync


def main() -> None:
    parser = argparse.ArgumentParser(prog="podcast-proxy")
    parser.add_argument("--log-level", default="INFO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--config", required=True)
    sync_parser.add_argument(
        "--podcast",
        action="append",
        dest="podcasts",
        default=[],
        help="limit the run to one or more podcast slugs",
    )

    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.add_argument("--config", required=True)
    rebuild_parser.add_argument(
        "--podcast",
        action="append",
        dest="podcasts",
        default=[],
        help="limit the run to one or more podcast slugs",
    )

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("--config", required=True)
    refresh_parser.add_argument(
        "--podcast",
        action="append",
        dest="podcasts",
        default=[],
        help="limit the run to one or more podcast slugs",
    )

    rebuild_images_parser = subparsers.add_parser("rebuild-images")
    rebuild_images_parser.add_argument("--config", required=True)
    rebuild_images_parser.add_argument(
        "--podcast",
        action="append",
        dest="podcasts",
        default=[],
        help="limit the run to one or more podcast slugs",
    )

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
        index_path = sync(config, rebuild=False, podcast_slugs=args.podcasts)
        print(index_path)
        return

    if args.command == "rebuild":
        config = load_config(args.config)
        index_path = sync(config, rebuild=True, podcast_slugs=args.podcasts)
        print(index_path)
        return

    if args.command == "refresh":
        config = load_config(args.config)
        index_path = sync(config, rebuild_images=True, podcast_slugs=args.podcasts)
        print(index_path)
        return

    if args.command == "rebuild-images":
        logging.warning(
            "'rebuild-images' is deprecated; use 'refresh' instead"
        )
        config = load_config(args.config)
        index_path = sync(config, rebuild_images=True, podcast_slugs=args.podcasts)
        print(index_path)
        return

    if args.command == "serve":
        config = load_config(args.config)
        serve(
            config.public_dir,
            args.port,
            username=config.http.basic_auth_username,
            password=config.http.basic_auth_password,
        )


def serve(directory: Path, port: int, *, username: str, password: str) -> None:
    handler = partial_handler(directory, username=username, password=password)
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as server:
        print(
            f"Serving {directory} on http://0.0.0.0:{port} "
            f"(HTTP Basic Auth user: {username})"
        )
        server.serve_forever()


def partial_handler(
    directory: Path,
    *,
    username: str,
    password: str,
) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=os.fspath(directory), **kwargs)

        def send_head(self):  # type: ignore[override]
            if not _is_authorized(
                self.headers.get("Authorization"),
                username=username,
                password=password,
            ):
                self._send_auth_challenge()
                return None
            return super().send_head()

        def _send_auth_challenge(self) -> None:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Podfix"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(b"Authentication required.\n")

    return Handler


def _is_authorized(
    authorization_header: str | None,
    *,
    username: str,
    password: str,
) -> bool:
    if not authorization_header:
        return False
    scheme, _, value = authorization_header.partition(" ")
    if scheme.lower() != "basic" or not value:
        return False
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    provided_username, separator, provided_password = decoded.partition(":")
    if not separator:
        return False
    return secrets.compare_digest(provided_username, username) and secrets.compare_digest(
        provided_password,
        password,
    )


if __name__ == "__main__":
    main()
