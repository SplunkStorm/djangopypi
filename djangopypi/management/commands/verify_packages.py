from djangopypi.models import Distribution
from django.conf import settings

from django.core.management.base import BaseCommand
from optparse import OptionParser, make_option

import sys
import datetime
import logging
import hashlib

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--log',
            dest='log_file',
            default=None,
            help='Log the results of the script to a file',
        ),
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._parse_args()
        self._configure_log()

    def _parse_args(self):
        parser = OptionParser()
        parser.add_options(self.option_list)
        self.options, _ = parser.parse_args()

    def _configure_log(self):
        self._log = logging.getLogger(__file__)

        formatter = logging.Formatter(
            '%(filename)s - %(levelname)s - %(message)s'
        )

        if self.options.log_file:
            file_log = logging.FileHandler(self.options.log_file)
            file_log.setLevel(logging.INFO)
            file_log.setFormatter(formatter)
            self._log.addHandler(file_log)
        
        console_log = logging.StreamHandler()
        console_log.setLevel(logging.DEBUG)
        console_log.setFormatter(formatter)
        self._log.addHandler(console_log)

        self._log.setLevel(logging.DEBUG)

    def log(self, dist, message):
        self._log.critical(
            message +
            ' Package: ' + dist.release.package.name +
            ' Version: ' + dist.release.version +
            ' Type: ' + dist.filetype +
            ' Path: ' + dist.content.path
        )

    def handle(self, *args, **kwargs):
        ''' Loops over the database checking that each file exists '''
        time_stamp = datetime.datetime.now().strftime('%c')
        self._log.info('Started verification %s' % time_stamp)

        okay = 0

        for dist in Distribution.objects.all():
            if not dist.content.storage.exists(dist.content.path):
                self.log(dist, 'Distribution not found')
            else:
                if not self.valid_md5(dist):
                    self.log(dist, 'Distribution md5 mismatch')
                else:
                    okay += 1


        time_stamp = datetime.datetime.now().strftime('%c')
        self._log.info('Finished verification at %s: %d/%d correct' % (
            time_stamp, okay, Distribution.objects.count()
        ))

    def valid_md5(self, dist):
        assert dist.content.storage.exists(dist.content.path)

        BLOCKSIZE = 1024*1024

        def hexify(s):
            return ('%02x'*len(s)) % tuple(map(ord, s))

        dist.content.open()
        sum = hashlib.md5()

        while 1:
            block = dist.content.read(BLOCKSIZE)
            if not block:
                break
            sum.update(block)

        dist.content.close()
        
        calculated_md5 = hexify(sum.digest())

        return str(calculated_md5) == str(dist.md5_digest)
