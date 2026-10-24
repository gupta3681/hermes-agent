"""Loopback object server and synthetic records for runtime channel-reader tests."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
from threading import Lock, Thread
from urllib.parse import parse_qs, urlsplit
import uuid
import xml.sax.saxutils

from hermes_cli.release_channels import ChannelReader, canonical_json, package_versions

_SERVERS = {}


@contextmanager
def object_server():
    objects, headers, requests = {}, {}, []
    lock = Lock()
    faults = {"lose_put": False, "stale_public": None, "conflict": None, "bad_pagination": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            with lock:
                requests.append(("GET", self.path))
                if "list-type" in query:
                    prefix = query.get("prefix", [""])[0]
                    keys = sorted(k for k in objects if k.startswith(prefix))
                    start = int(query.get("continuation-token", ["0"])[0])
                    page = keys[start:start + 2]
                    more = start + 2 < len(keys)
                    body = ("<ListBucketResult>" + "".join(
                        f"<Contents><Key>{xml.sax.saxutils.escape(k)}</Key></Contents>" for k in page)
                        + f"<IsTruncated>{str(more).lower()}</IsTruncated>"
                        + (f"<NextContinuationToken>{start + 2}</NextContinuationToken>" if more else "")
                        + "</ListBucketResult>").encode()
                    if faults["bad_pagination"]:
                        body = b"<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>"
                    etag = None
                else:
                    key = parsed.path.removeprefix("/bucket/")
                    body = objects.get(key)
                    if not self.headers.get("Authorization") and faults["stale_public"] is not None:
                        body = faults["stale_public"]
                    etag = '"' + hashlib.sha256(body).hexdigest() + '"' if body is not None else None
                self.send_response(200 if body is not None else 404)
                if etag:
                    self.send_header("ETag", etag)
                self.end_headers()
                if body is not None:
                    self.wfile.write(body)

        def do_PUT(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            key = self.path.removeprefix("/bucket/")
            with lock:
                requests.append(("PUT", key))
                if faults["conflict"]:
                    conflict = faults["conflict"]
                    faults["conflict"] = None
                    conflict(objects, key)
                old = objects.get(key)
                etag = '"' + hashlib.sha256(old).hexdigest() + '"' if old is not None else None
                conflict = ((self.headers.get("If-None-Match") == "*" and old is not None)
                            or (self.headers.get("If-Match") is not None and self.headers["If-Match"] != etag))
                if conflict:
                    self.send_response(412)
                    self.end_headers()
                    return
                objects[key] = body
                headers[key] = dict(self.headers)
                if faults["lose_put"]:
                    faults["lose_put"] = False
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                self.send_response(200)
                self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    _SERVERS[url] = objects
    try:
        yield url, objects, headers, requests, faults
    finally:
        _SERVERS.pop(url, None)
        server.shutdown()
        server.server_close()
        thread.join()


def preview_identity(name, token):
    pascal = f"FixtureChannel{token}"
    return {"token": token, "displayName": f"Fixture {name}", "appId": f"test.channel.h{token}",
            "appNamePascal": pascal, "artifactNamePascal": pascal, "cliName": f"fixture-{name}",
            "windowsExecutableName": pascal, "msixAppIdWithOrg": f"Fixture.{pascal}"}


class ChannelRecords:
    """Seed synthetic objects directly; no signing, release gates or publication implementation."""
    def __init__(self, url):
        self.objects = _SERVERS[url]
        self.base = url + "/bucket"
        self.reader = ChannelReader(self.base, repository="example/hermes-agent")

    def _read(self, name):
        return json.loads(self.objects[f"releases/channels/{name}.json"]), None

    def create(self, name):
        record = {"schema": 1, "name": name, "repository": "example/hermes-agent",
                  "policy": "preview", "state": "active", "revision": 1,
                  "nextSequence": 1, "head": None, "identity": preview_identity(name, "a" * 16)}
        self.objects[f"releases/channels/{name}.json"] = canonical_json(record)
        return deepcopy(record)

    def allocate(self, name, commit, source_version):
        record, _ = self._read(name)
        sequence = record["nextSequence"]
        version, windows = package_versions(sequence)
        request = {"schema": 1, "buildId": uuid.uuid4().hex, "channel": name, "sequence": sequence,
                   "repository": record["repository"], "commit": commit, "sourceVersion": source_version,
                   "version": version, "windowsVersion": windows, "identity": record["identity"],
                   "bundleEnv": {}, "publicBase": self.base}
        record.update(nextSequence=sequence + 1, revision=record["revision"] + 1)
        self.objects[f"releases/channels/{name}.json"] = canonical_json(record)
        return request


def publisher(url):
    return ChannelRecords(url)
