from djangopypi.models import *
from djangopypi import conf
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.datastructures import MultiValueDict

from pkginfo import BDist, SDist

from optparse import OptionParser, make_option
import textwrap
import sys, os, shutil

class Command(BaseCommand):
    args = '<foo-1.2.3.tar.gz bar-1.9.zip baz-2.2.egg>'
    help = 'Imports one or more packages to the dists folder and adds ' \
            'package metadata to the database'

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
                Group given immediate download permissions to the packages.
                WARNING: If no group is specified, the packages will be
                uploaded with world-readable permissions''')
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
        )
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self._parse_args()

    def _parse_args(self):
        parser = OptionParser()
        parser.add_options(self.option_list)
        self.options, _ = parser.parse_args()
        if self.options.download_perm_group:
            try:
                self.download_perm_group = Group.objects.get(
                                        name=self.options.download_perm_group)
            except Group.DoesNotExist:
                raise SystemExit('The download permissions group doesn\'t exist')
        else:
            self.download_perm_group = None

        try:
            self.owner_group = Group.objects.get(name=self.options.owner_group)
        except Group.DoesNotExist:
            raise SystemExit('The owner group specified doesn\'t exist')

        try:
            self.upload_user = User.objects.get(username=self.options.upload_user)
        except User.DoesNotExist:
            raise SystemExit('The upload user specified doesn\'t exist')

    def handle(self, *args, **kwargs):
        for filename in args:
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
                    print >>sys.stderr, 'Ignoring: %s:' % filename

            except ValueError, e:
                if 'No PKG-INFO in archive' in e.message:
                    if self.options.old_products:
                        if filename.endswith('.tar.gz') or \
                                                    filename.endswith('.tgz'):

                            self._log(
                                filename,
                                None,
                                *self._old_style_product(filename)
                            )
                            continue
                print >>sys.stderr, 'Importing: %s: ERROR\n\t%s' % (
                                                            filename, e.message)


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

        print >>sys.stderr, textwrap.dedent('''\
            Importing %s %s: %s. [Created Package(): %r. Created Release(): %r.]
            ''' % (filename, old_style, result, pkg_created, release_created))

    def _add_dist(self, dist_data):
        package, created_package  = Package.objects.get_or_create(
            name=dist_data.name,
        )

        if created_package:
            package.owners.add(self.owner_group)
            if self.download_perm_group:
                package.download_permissions.add(self.download_perm_group)

        release, created_release = Release.objects.get_or_create(
            package=package,
            version=dist_data.version,
            metadata_version=dist_data.metadata_version,
            package_info=self._package_info(dist_data)
        )

        new_path, dist_file = self._copy_dist_file()
        if dist_file:
            distribution, created_dist = Distribution.objects.get_or_create(
                release = release,
                content=dist_file,
                md5_digest=self._md5_digest(),
                filetype=self._get_filetype(dist_data),
                pyversion=self._get_pyversion(dist_data),
                uploader=self.upload_user,
            )
        else:
            created_dist = False

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
                print >>sys.stderr, 'Could not find %s in the dist data.' % f

        package_info = dict(info)

        return package_info

    def _copy_dist_file(self):
        '''Move the file to the media folder, then return the new location'''
        upload_directory = os.path.join(
            settings.MEDIA_ROOT,
            conf.RELEASE_UPLOAD_TO
        )

        try:
            new_path = os.path.join(upload_directory, os.path.basename(self._curfile))
            if not os.path.exists(new_path):
                shutil.copyfile(self._curfile, new_path)
            else:
                print >>sys.stderr, '\tFile already exists: %s' % new_path

            media_path = os.path.join(
                conf.RELEASE_UPLOAD_TO,
                os.path.basename(self._curfile)
            )

            return new_path, media_path
        except IOError:
            print >>sys.stderr, 'Could not copy file to upload directory'
            return None

    def _old_style_product(self, filename):
        try:
            package_name, version = self._parse_product_filename(filename)
        except:
            print >>sys.stderr, 'Couldn\'t parse the product filename'
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
