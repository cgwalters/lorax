#
# dnfhelper.py
#
# Copyright (C) 2010-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#                     Brian C. Lane <bcl@redhat.com>
#

import logging
logger = logging.getLogger("pylorax.dnfhelper")
import dnf
import collections
import time
import pylorax.output as output

__all__ = ['LoraxDownloadCallback', 'LoraxRpmCallback']

def _paced(fn):
    """Execute `fn` no more often then every 2 seconds."""
    def paced_fn(self, *args):
        now = time.time()
        if now - self.last_time < 2:
            return
        self.last_time = now
        return fn(self, *args)
    return paced_fn


class LoraxDownloadCallback(dnf.callback.DownloadProgress):
    def __init__(self):
        self.downloads = collections.defaultdict(int)
        self.last_time = time.time()
        self.total_files = 0
        self.total_size = 0

        self.pkgno = 0
        self.total = 0

        self.output = output.LoraxOutput()

    @_paced
    def _update(self):
        msg = "Downloading %(pkgno)s / %(total_files)s RPMs, " \
              "%(downloaded)s / %(total_size)s (%(percent)d%%) done.\n"
        downloaded = sum(self.downloads.values())
        vals = {
            'downloaded'  : downloaded,
            'percent'     : int(100 * downloaded/self.total_size),
            'pkgno'       : self.pkgno,
            'total_files' : self.total_files,
            'total_size'  : self.total_size
        }
        self.output.write(msg % vals)

    def end(self, payload, status, err_msg):
        nevra = str(payload)
        if status is dnf.callback.STATUS_OK:
            self.downloads[nevra] = payload.download_size
            self.pkgno += 1
            self._update()
            return
        logger.critical("Failed to download '%s': %d - %s", nevra, status, err_msg)

    def progress(self, payload, done):
        nevra = str(payload)
        self.downloads[nevra] = done
        self._update()

    def start(self, total_files, total_size):
        self.total_files = total_files
        self.total_size = total_size


class LoraxRpmCallback(dnf.callback.LoggingTransactionDisplay):
    def __init__(self, queue):
        super(LoraxRpmCallback, self).__init__()
        self._queue = queue
        self._last_ts = None
        self.cnt = 0

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        if action == self.PKG_INSTALL and te_current == 0:
            # do not report same package twice
            if self._last_ts == ts_current:
                return
            self._last_ts = ts_current

            msg = '(%d/%d) %s.%s' % \
                (ts_current, ts_total, package.name, package.arch)
            self.cnt += 1
            self._queue.put(('install', msg))
        elif action == self.TRANS_POST:
            self._queue.put(('post', None))
