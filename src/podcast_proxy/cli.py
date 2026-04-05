from __future__ import annotations

import argparse
import base64
import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import secrets
import shutil
from typing import BinaryIO
from urllib.parse import urlsplit

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
    sync_parser.add_argument(
        "--clean-stale",
        action="store_true",
        help="delete stale published files that are no longer referenced by state",
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
    rebuild_parser.add_argument(
        "--clean-stale",
        action="store_true",
        help="delete stale published files that are no longer referenced by state",
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
    refresh_parser.add_argument(
        "--clean-stale",
        action="store_true",
        help="delete stale published files that are no longer referenced by state",
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
    rebuild_images_parser.add_argument(
        "--clean-stale",
        action="store_true",
        help="delete stale published files that are no longer referenced by state",
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
        index_path = sync(
            config,
            rebuild=False,
            podcast_slugs=args.podcasts,
            clean_stale=args.clean_stale,
        )
        print(index_path)
        return

    if args.command == "rebuild":
        config = load_config(args.config)
        index_path = sync(
            config,
            rebuild=True,
            podcast_slugs=args.podcasts,
            clean_stale=args.clean_stale,
        )
        print(index_path)
        return

    if args.command == "refresh":
        config = load_config(args.config)
        index_path = sync(
            config,
            rebuild_images=True,
            podcast_slugs=args.podcasts,
            clean_stale=args.clean_stale,
        )
        print(index_path)
        return

    if args.command == "rebuild-images":
        logging.warning(
            "'rebuild-images' is deprecated; use 'refresh' instead"
        )
        config = load_config(args.config)
        index_path = sync(
            config,
            rebuild_images=True,
            podcast_slugs=args.podcasts,
            clean_stale=args.clean_stale,
        )
        print(index_path)
        return

    if args.command == "serve":
        config = load_config(args.config)
        serve(
            config.public_dir,
            args.port,
            username=config.http.basic_auth_username,
            password=config.http.basic_auth_password,
            media_path_token=config.podcasts[0].media_path_token,
        )


def serve(
    directory: Path,
    port: int,
    *,
    username: str,
    password: str,
    media_path_token: str,
) -> None:
    handler = partial_handler(
        directory,
        username=username,
        password=password,
        media_path_token=media_path_token,
    )
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
    media_path_token: str,
) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._range: tuple[int, int] | None = None
            super().__init__(*args, directory=os.fspath(directory), **kwargs)

        def send_head(self):  # type: ignore[override]
            if not self._is_public_media_request() and not _is_authorized(
                self.headers.get("Authorization"),
                username=username,
                password=password,
            ):
                self._send_auth_challenge()
                return None
            path = self.translate_path(self.path)
            if os.path.isdir(path):
                self._range = None
                return super().send_head()
            ctype = self.guess_type(path)
            try:
                handle = open(path, "rb")
            except OSError:
                self.send_error(404, "File not found")
                return None
            try:
                fs = os.fstat(handle.fileno())
                file_size = fs.st_size
                range_request = _parse_range_header(
                    self.headers.get("Range"),
                    file_size,
                )
                if range_request is None:
                    self._range = None
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(file_size))
                else:
                    start, end = range_request
                    self._range = (start, end)
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(end - start + 1))
                    handle.seek(start)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header(
                    "Last-Modified",
                    self.date_time_string(fs.st_mtime),
                )
                if self._is_public_media_request():
                    self.send_header(
                        "X-Robots-Tag",
                        "noindex, nofollow, noarchive, nosnippet",
                    )
                    self.send_header("Cache-Control", "private")
                self.end_headers()
                return handle
            except BaseException:
                handle.close()
                raise

        def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:
            if self._range is None:
                shutil.copyfileobj(source, outputfile)
                return
            start, end = self._range
            del start
            remaining = end - source.tell() + 1
            while remaining > 0:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)

        def _send_auth_challenge(self) -> None:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Podfix"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(b"Authentication required.\n")

        def _is_public_media_request(self) -> bool:
            return (
                _public_media_relative_path(
                    self.path,
                    media_path_token=media_path_token,
                )
                is not None
            )

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


def _parse_range_header(
    range_header: str | None,
    file_size: int,
) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes=") or file_size <= 0:
        return None
    value = range_header[6:].strip()
    if "," in value:
        return None
    start_text, separator, end_text = value.partition("-")
    if not separator:
        return None
    try:
        if start_text:
            start = int(start_text)
            end = file_size - 1 if not end_text else int(end_text)
        else:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            if suffix_length >= file_size:
                return (0, file_size - 1)
            start = file_size - suffix_length
            end = file_size - 1
    except ValueError:
        return None
    if start < 0 or end < start or start >= file_size:
        return None
    return (start, min(end, file_size - 1))


def _public_media_relative_path(
    request_path: str,
    *,
    media_path_token: str,
) -> str | None:
    parsed = urlsplit(request_path)
    path = parsed.path.strip("/")
    prefix = f"{media_path_token.strip('/')}/"
    if not path.startswith(prefix):
        return None
    if not path.lower().endswith(".mp3"):
        return None
    return path


if __name__ == "__main__":
    main()
