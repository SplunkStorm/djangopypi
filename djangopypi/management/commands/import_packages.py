from djangopypi.models import *
from djangopypi import conf
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.datastructures import MultiValueDict
from django.db.utils import IntegrityError
from django.db import transaction

from pkginfo import BDist, SDist

from optparse import OptionParser, make_option
import textwrap
import sys, os, shutil

import logging

class Command(BaseCommand):
    args = '<foo-1.2.3.tar.gz bar-1.9.zip baz-2.2.egg>'
    help = 'Imports one or more packages to the dists folder and adds ' \
            'package metadata to the database'

    LOG_FILENAME = '/tmp/package_import.log'

    default_group = Group.objects.all()[0].name
    default_user = User.objects.filter(is_superuser=True)[0].username

    option_list = BaseCommand.option_list + (
        make_option('--owner-group',
            dest='owner_group',
            default=default_group,
            help='The group owner of the imported packages'
        ),
        make_option('--download-perm-group',
            dest='download_perm_group',
            default=None,
            help=textwrap.dedent('''\
                A comma-separated list of Group names given immediate download
                permissions to the packages. WARNING: If no group is specified,
                the packages will be uploaded with world-readable permissions'''
            )
        ),
        make_option('--upload-user',
            dest='upload_user',
            default=default_user,
            help='The user that uploaded the packages - defaults to superuser',
        ),
        make_option('--old-style-products',
            dest='old_products',
            action='store_true',
            default=False,
            help='Treat archives containing no PKG-INFO as old-style products',
        ),
        make_option('--log',
            dest='log_file',
            default=LOG_FILENAME,
            help='Log the migration process to a file',
        ),
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._parse_args()
        self._configure_log()

    def _configure_log(self):
        self.log = logging.getLogger(__file__)

        formatter = logging.Formatter(
                    "%(asctime)s - %(filename)s - %(levelname)s - %(message)s")

        # Log everything to the file log
        file_log = logging.FileHandler(self.options.log_file)
        file_log.setLevel(logging.DEBUG)

        # Log only INFO or higher to console
        console_log = logging.StreamHandler()
        console_log.setLevel(logging.INFO)

        file_log.setFormatter(formatter)
        console_log.setFormatter(formatter)

        self.log.addHandler(file_log)
        self.log.addHandler(console_log)

        self.log.setLevel(logging.DEBUG)

    def _parse_args(self):
        parser = OptionParser()
        parser.add_options(self.option_list)
        self.options, _ = parser.parse_args()
        if self.options.download_perm_group:
            try:
                self.download_perm_groups = []
                for group in self.options.download_perm_group.split(','):
                    self.download_perm_groups.append(
                        Group.objects.get(name=group)
                    )
            except Group.DoesNotExist:
                raise SystemExit('The download permissions group doesn\'t exist')
        else:
            self.download_perm_groups = []

        try:
            self.owner_group = Group.objects.get(name=self.options.owner_group)
        except Group.DoesNotExist:
            raise SystemExit('The owner group specified doesn\'t exist')

        try:
            self.upload_user = User.objects.get(username=self.options.upload_user)
        except User.DoesNotExist:
            raise SystemExit('The upload user specified doesn\'t exist')

    def handle(self, *args, **kwargs):
        self.log.debug('import packages script started')
        for filename in args:
            self.log.debug('File: %s' % filename)

            self._curfile = filename
            try:
                if filename.endswith('.zip') or filename.endswith('.tar.gz') or \
                                                        filename.endswith('.tgz'):
                    package = SDist(self._curfile)
                    self._log(filename, package, *self._add_dist(package))
                elif filename.endswith('.egg'):
                    package = BDist(self._curfile)
                    self._log(filename, package, *self._add_dist(package))
                else:
                    self.log.debug('Ignoring: %s:' % filename)

            except ValueError, e:
                if 'No PKG-INFO in archive' in e.message and \
                                            self.options.old_products and \
                                            (filename.endswith('.tar.gz') or \
                                            filename.endswith('.tgz')):
                    self._log(filename, None, *self._old_style_product(filename))
                    continue
                self.log.error('Could not import %s: %s' % (
                                                        filename, e.message))
        self.log.debug('import packages script completed')


    def _log(self, filename, package, pkg_created, release_created, dist_created):
        """ Log logic """
        if dist_created:
            result = 'Success'
        else:
            result = 'FAILED'

        if not package:
            old_style = '[OLD STYLE PRODUCT]'
        else:
            old_style = ''

        log_string = textwrap.dedent('''\
            Importing %s %s: %s. [Created Package(): %r. Created Release(): %r.]\
            ''' % (filename, old_style, result, pkg_created, release_created))

        if dist_created:
            self.log.info(log_string)
        else:
            self.log.critical(log_string)

    @transaction.autocommit
    def _add_dist(self, dist_data):

        try:
            package, created_package  = Package.objects.get_or_create(
                name=dist_data.name,
            )
        except IntegrityError:
            transaction.rollback()
            self.log.critical('Cannot add package name %r: file %s error' % (
                              dist_data.name, self._curfile))
            return False, False, False

        if created_package:
            package.owners.add(self.owner_group)
            for group in self.download_perm_groups:
                package.download_permissions.add(group)

        created_release = False
        try:
            release = Release.objects.get(
                version=dist_data.version,
                package=package,
            )
        except Release.DoesNotExist:
            release = Release.objects.create(
                package=package,
                version=dist_data.version,
                metadata_version=dist_data.metadata_version,
                package_info=self._package_info(dist_data)
            )
            created_release = True

        created_dist = False
        new_path, dist_file = self._copy_dist_file()

        try:
            distribution = Distribution.objects.get(
                release=release,
                content=dist_file,
            )
        except Distribution.DoesNotExist:
            if dist_file:
                try:
                    distribution = Distribution.objects.create(
                        release = release,
                        content=dist_file,
                        md5_digest=self._md5_digest(),
                        filetype=self._get_filetype(dist_data),
                        pyversion=self._get_pyversion(dist_data),
                        uploader=self.upload_user,
                    )
                    created_dist = True
                except IntegrityError:
                    self.log.error('Could not import %s: Already have this ' \
                                   'spec package.' % (self._curfile,))
                    transaction.rollback()

        return created_package, created_release, created_dist

    def _package_info(self, dist_data):
        fields = list(conf.METADATA_FIELDS[dist_data.metadata_version])

        # pkginfo gets PEP241 wrong, calling platform 'platforms'.
        if 'platform' in fields:
            fields.remove('platform')
            fields.append('platforms')

        info = []
        for f in fields:
            try:
                if isinstance(getattr(dist_data, f), list):
                    info.append((f, getattr(dist_data, f)))
                else:
                    info.append((f, [getattr(dist_data, f)]))
            except AttributeError:
                self.log.debug('Could not find %s in the dist data.' % f)

        package_info = dict(info)

        return package_info

    def _copy_dist_file(self):
        '''Move the file to the media folder, then return the new location'''
        content_field = Distribution._meta.get_field('content')

        upload_path = os.path.join(
            content_field.storage.location,
            content_field.upload_to(None, os.path.basename(self._curfile))
        )

        try:
            if not os.path.exists(upload_path):
                # Create the directory if necessary
                upload_folder = os.path.dirname(upload_path)
                if not os.path.exists(upload_folder):
                    os.mkdir(upload_folder)
                shutil.copyfile(self._curfile, upload_path)
            else:
                self.log.warn('File already exists: %s' % upload_path)

            media_path = content_field.upload_to(None, os.path.basename(self._curfile))

            return upload_path, media_path
        except IOError:
            self.log.critical('Could not copy file to upload directory %s' % upload_path)
            return None

    def _old_style_product(self, filename):
        try:
            package_name, version = self._parse_product_filename(filename)
        except:
            self.log.error('Couldn\'t parse the product filename "%s"' % filename)
            return False, False, False

        # Prompt the user to see if satisfactory
        print 'Detected an old-style package: %s' % filename
        print 'Using package name: %s, version: %s' % (package_name, version)
        accepted = raw_input('Accept? [y/N] ')
        if accepted.lower() != 'y':
            print 'Not accepted. Skipping %s' % filename
            return False, False, False

        package, created_package = Package.objects.get_or_create(
            name=package_name
        )

        release, created_release = Release.objects.get_or_create(
            package=package,
            version=version,
            metadata_version='1.0',
            package_info={},
        )

        new_path, dist_file = self._copy_dist_file()
        if dist_file:
            dist, created_dist = Distribution.objects.get_or_create(
                release=release,
                content=dist_file,
                md5_digest=self._md5_digest(),
                uploader=self.upload_user,
            )

        return created_package, created_release, created_dist

    def _parse_product_filename(self, filename):
        bn = os.path.basename(filename)
        split_bn = bn.split('-', 1)

        package_name = split_bn[0]

        version_string = os.path.splitext(split_bn[1])[0]
        if version_string[-4:] == '.tar':
            version_string = version_string[:-4]

        return package_name, version_string

    def _md5_digest(self):
        import md5

        BLOCKSIZE = 1024*1024

        def hexify(s):
            return ("%02x"*len(s)) % tuple(map(ord, s))

        f = open(self._curfile, "rb")
        sum = md5.new()
        while 1:
            block = f.read(BLOCKSIZE)
            if not block:
                break
            sum.update(block)
        f.close()
        return hexify(sum.digest())

    def _get_pyversion(self, dist_data):
        #TODO: Erm pkginfo can haz pyversion?!
        return ''

    def _get_filetype(self, dist_data):
        if isinstance(dist_data, SDist):
            return 'sdist'
        elif isinstance(dist_data, BDist):
            return 'bdist_egg'
        else:
            return ''
