#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Charm the application."""

from __future__ import annotations

import logging
import pathlib
import typing

import common
import ops

# TODO: switch to recommended form `from charmlibs import pathops`
#       after next pyright release fixes:
#       https://github.com/microsoft/pyright/issues/10203
import charmlibs.pathops as pathops

if typing.TYPE_CHECKING:
    from typing import Sequence

logger = logging.getLogger(__name__)

CONTAINER = 'workload'


class Charm(common.Charm):
    """Charm the application."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on[CONTAINER].pebble_ready, self._on_pebble_ready)
        self.container = self.unit.get_container(CONTAINER)
        self.root = pathops.ContainerPath(pathlib.Path('/', 'tmp'), container=self.container)

    def _on_pebble_ready(self, event: ops.PebbleReadyEvent):
        """Handle pebble-ready event."""
        self.unit.status = ops.ActiveStatus()

    def remove_path(self, path: pathops.PathProtocol, recursive: bool = False) -> None:
        assert isinstance(path, pathops.ContainerPath)
        self.container.remove_path(str(path), recursive=recursive)

    def exec(self, cmd: Sequence[str]) -> None:
        self.container.exec(list(cmd))


if __name__ == '__main__':  # pragma: nocover
    ops.main(Charm)
