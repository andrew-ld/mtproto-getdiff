# Copyright (C) 2019 andrew-ld <https://github.com/andrew-ld>
#
# This file is part of mtproto-getdiff.
#
# mtproto-getdiff is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# mtproto-getdiff is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with mtproto-getdiff. If not, see <http://www.gnu.org/licenses/>.


from os import mkdir
from json import dumps
from queue import Queue
from pyrogram import Client
from threading import Thread
from os.path import isdir, isfile
from pyrogram.api.core.object import Encoder
from pyrogram.api.types.updates.difference import Difference
from pyrogram.api.functions.updates.get_difference import GetDifference
from pyrogram.api.types.updates.difference_slice import DifferenceSlice
from pyrogram.api.types.updates.difference_empty import DifferenceEmpty
from pyrogram.api.types.updates.difference_too_long import DifferenceTooLong
from pyrogram.api.errors.exceptions.internal_server_error_500 import InternalServerError
from pyrogram.api.errors.exceptions.unauthorized_401 import Unauthorized


APP_ID = 1
APP_HASH = "b6b154c3707471f5339bd661645ed3d6"

OUT_DIR = "out"
THREADS = 8
TOKENS_FILE = "tokens.txt"
WORK_DIR = "sessions"


def bound_get_diff(queue: Queue):
    while not queue.empty():
        token = queue.get_nowait()

        if not token:
            break

        get_diff(token)


def write_diff(out, diff):
    raw = dumps(diff, cls=Encoder)
    size = out.tell()

    if size != 0:
        out.seek(size - 1)
        raw = f", {raw[1:]}"

    out.write(raw)
    out.flush()


def get_diff(token: str):
    client = Client(token)
    client.workers = 1
    client.no_updates = True

    client.api_id = APP_ID
    client.api_hash = APP_HASH
    client.workdir = WORK_DIR

    try:
        client.start()
    except Exception:
        return

    uid = client.get_me().id
    req = GetDifference(1, 1, 0)
    out = open(f"{OUT_DIR}/{uid}", "w")

    while True:

        try:
            diff = client.send(req)

        except InternalServerError:
            continue

        except Unauthorized:
            break

        if isinstance(diff, DifferenceSlice):
            write_diff(out, diff.new_messages)

            req.pts = diff.intermediate_state.pts
            req.qts = diff.intermediate_state.qts
            req.date = diff.intermediate_state.date

            print(f"next pts for {uid} = {req.pts}")

        elif isinstance(diff, Difference):
            write_diff(out, diff.new_messages)
            break

        elif isinstance(diff, DifferenceTooLong):
            req.pts = diff.pts

        elif isinstance(diff, DifferenceEmpty):
            break

    if client.is_started:
        client.stop()

    client.save_session()
    out.close()


def main(tokens: set):
    queue = Queue()
    threads = []

    for token in tokens:
        queue.put_nowait(token)

    for _ in range(THREADS):
        thread = Thread()
        threads.append(thread)

        thread._target = bound_get_diff
        thread._args = (queue,)

        thread.start()

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    if not isdir(WORK_DIR):
        mkdir(WORK_DIR)

    if not isdir(OUT_DIR):
        mkdir(OUT_DIR)

    if not isfile(TOKENS_FILE):
        raise FileNotFoundError

    _tokens = open(TOKENS_FILE).readlines()
    _tokens = set(x.strip() for x in _tokens)
    _tokens = set(x[3:] if x[:3] == "bot" else x for x in _tokens)

    main(_tokens)
