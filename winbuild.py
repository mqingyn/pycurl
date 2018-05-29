# Bootstrap python binary:
# http://www.python.org/ftp/python/3.3.5/python-3.3.5.msi
# Then execute:
# msiexec /i c:\dev\build-pycurl\archives\python-3.3.5.msi /norestart /passive InstallAllUsers=1 Include_test=0 Include_doc=0 Include_launcher=0 Include_ckltk=0 TargetDir=c:\dev\32\python33
# msvc9/vs2008 express:
# http://go.microsoft.com/?linkid=7729279
# msvc10/vs2010 express:
# http://go.microsoft.com/?linkid=9709949
# for 64 bit builds, then install 2010 sp1:
# http://go.microsoft.com/fwlink/?LinkId=210710
# ... and windows 7 sdk (because sp1 compiler update refuses to install
# without it):
# http://www.microsoft.com/en-us/download/details.aspx?id=8279
# or http://www.microsoft.com/en-us/download/details.aspx?id=8442
# then install sp1 compiler update:
# https://www.microsoft.com/en-us/download/details.aspx?id=4422
# msvc14/vs2015 community:
# https://www.visualstudio.com/en-us/downloads/download-visual-studio-vs.aspx
#
# OpenSSL build resources including 64-bit builds:
# http://stackoverflow.com/questions/158232/how-do-you-compile-openssl-for-x64
# https://wiki.openssl.org/index.php/Compilation_and_Installation
# http://developer.covenanteyes.com/building-openssl-for-visual-studio/
#
# NASM:
# http://www.nasm.us/
# ActiveState Perl:
# http://www.activestate.com/activeperl/downloads

class Config:
    '''User-adjustable configuration.
    
    This class contains version numbers for dependencies,
    which dependencies to use,
    and where various binaries, headers and libraries are located in the filesystem.
    '''
    
    # work directory for downloading dependencies and building everything
    root = 'c:/dev/build-pycurl'
    # where msysgit is installed
    git_root = 'c:/program files/git'
    msysgit_bin_paths = [
        "c:\\Program Files\\Git\\bin",
        "c:\\Program Files\\Git\\usr\\bin",
        #"c:\\Program Files\\Git\\mingw64\\bin",
    ]
    # where NASM is installed, for building OpenSSL
    nasm_path = ('c:/dev/nasm', 'c:/program files/nasm', 'c:/program files (x86)/nasm')
    cmake_path = r"c:\Program Files\CMake\bin\cmake.exe"
    # where ActiveState Perl is installed, for building 64-bit OpenSSL
    activestate_perl_path = ('c:/perl64', r'c:\dev\perl64')
    # which versions of python to build against
    #python_versions = ['2.7.10', '3.2.5', '3.3.5', '3.4.3', '3.5.4', '3.6.2']
    # these require only vc9 and vc14
    python_versions = ['2.7.10', '3.5.4', '3.6.2']
    # where pythons are installed
    python_path_template = 'c:/dev/%(bitness)s/python%(python_release)s/python'
    vc_paths = {
        # where msvc 9/vs 2008 is installed, for python 2.6 through 3.2
        'vc9': None,
        # where msvc 10/vs 2010 is installed, for python 3.3 through 3.4
        'vc10': None,
        # where msvc 14/vs 2015 is installed, for python 3.5 through 3.6
        'vc14': None,
    }
    # whether to link libcurl against zlib
    use_zlib = True
    # which version of zlib to use, will be downloaded from internet
    zlib_version = '1.2.11'
    # whether to use openssl instead of winssl
    use_openssl = True
    # which version of openssl to use, will be downloaded from internet
    openssl_version = '1.1.0h'
    # whether to use c-ares
    use_cares = True
    cares_version = '1.14.0'
    # whether to use libssh2
    use_libssh2 = True
    libssh2_version = '1.8.0'
    use_nghttp2 = True
    nghttp2_version = '1.32.0'
    # which version of libcurl to use, will be downloaded from internet
    libcurl_version = '7.59.0'
    # virtualenv version
    virtualenv_version = '15.1.0'
    # whether to build binary wheels
    build_wheels = True
    # pycurl version to build, we should know this ourselves
    pycurl_version = '7.43.0.1'

    default_vc_paths = {
        # where msvc 9 is installed, for python 2.6-3.2
        'vc9': [
            'c:/program files (x86)/microsoft visual studio 9.0',
            'c:/program files/microsoft visual studio 9.0',
        ],
        # where msvc 10 is installed, for python 3.3-3.4
        'vc10': [
            'c:/program files (x86)/microsoft visual studio 10.0',
            'c:/program files/microsoft visual studio 10.0',
        ],
        # where msvc 14 is installed, for python 3.5-3.6
        'vc14': [
            'c:/program files (x86)/microsoft visual studio 14.0',
            'c:/program files/microsoft visual studio 14.0',
        ],
    }

import os, os.path, sys, subprocess, shutil, contextlib, zipfile, re
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

# https://stackoverflow.com/questions/35569042/python-3-ssl-certificate-verify-failed
import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

def short_python_versions(python_versions):
    return ['.'.join(python_version.split('.')[:2])
        for python_version in python_versions]

def needed_vc_versions(python_versions):
    return [vc_version for vc_version in config.vc_paths.keys()
        if vc_version in [
            PYTHON_VC_VERSIONS[short_python_version]
            for short_python_version in short_python_versions(python_versions)]]

def select_existing_path(paths):
    if isinstance(paths, list) or isinstance(paths, tuple):
        for path in paths:
            if os.path.exists(path):
                return path
        return paths[0]
    else:
        return paths

# This must be at top level as __file__ can be a relative path
# and changing current directory will break it
DIR_HERE = os.path.abspath(os.path.dirname(__file__))

def find_in_paths(binary, paths):
    for path in paths:
        if os.path.exists(os.path.join(path, binary)) or os.path.exists(os.path.join(path, binary + '.exe')):
            return os.path.join(path, binary)
    raise Exception('Could not find %s' % binary)

def check_call(cmd):
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        raise Exception('Failed to execute ' + str(cmd) + ': ' + str(type(e)) + ': ' +str(e))

class ExtendedConfig(Config):
    '''Global configuration that specifies what the entire process will do.
    
    Unlike Config, this class contains also various derived properties
    for convenience.
    '''
    
    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])
            
    @property
    def nasm_path(self):
        return select_existing_path(Config.nasm_path)
        
    @property
    def activestate_perl_path(self):
        return select_existing_path(Config.activestate_perl_path)
        
    @property
    def archives_path(self):
        return os.path.join(self.root, 'archives')
        
    @property
    def state_path(self):
        return os.path.join(self.root, 'state')
        
    @property
    def git_bin_path(self):
        #git_bin_path = os.path.join(git_root, 'bin')
        return ''
        
    @property
    def git_path(self):
        return os.path.join(self.git_bin_path, 'git')
        
    @property
    def rm_path(self):
        return find_in_paths('rm', self.msysgit_bin_paths)
        
    @property
    def sed_path(self):
        return find_in_paths('sed', self.msysgit_bin_paths)
        
    @property
    def tar_path(self):
        return find_in_paths('tar', self.msysgit_bin_paths)
        
    @property
    def activestate_perl_bin_path(self):
        return os.path.join(self.activestate_perl_path, 'bin')
        
    @property
    def winbuild_patch_root(self):
        return os.path.join(DIR_HERE, 'winbuild')

    @property
    def openssl_version_tuple(self):
        return tuple(
            int(part) if part < 'a' else part
            for part in re.sub(r'([a-z])', r'.\1', self.openssl_version).split('.')
        )

    @property
    def libssh2_version_tuple(self):
        return tuple(int(part) for part in self.libssh2_version.split('.'))

    @property
    def cares_version_tuple(self):
        return tuple(int(part) for part in self.cares_version.split('.'))

    @property
    def python_releases(self):
        return [PythonRelease('.'.join(version.split('.')[:2]))
            for version in self.python_versions]

PYTHON_VC_VERSIONS = {
    '2.6': 'vc9',
    '2.7': 'vc9',
    '3.2': 'vc9',
    '3.3': 'vc10',
    '3.4': 'vc10',
    '3.5': 'vc14',
    '3.6': 'vc14',
}

def mkdir_p(path):
    if not os.path.exists(path):
        os.makedirs(path)

def fetch(url, archive=None):
    if archive is None:
        archive = os.path.basename(url)
    if not os.path.exists(archive):
        sys.stdout.write("Fetching %s\n" % url)
        sys.stdout.flush()
        io = urlopen(url)
        tmp_path = os.path.join(os.path.dirname(archive),
            '.%s.part' % os.path.basename(archive))
        with open(tmp_path, 'wb') as f:
            while True:
                chunk = io.read(65536)
                if len(chunk) == 0:
                    break
                f.write(chunk)
        os.rename(tmp_path, archive)

def fetch_to_archives(url):
    mkdir_p(config.archives_path)
    path = os.path.join(config.archives_path, os.path.basename(url))
    fetch(url, path)

@contextlib.contextmanager
def in_dir(dir):
    old_cwd = os.getcwd()
    try:
        os.chdir(dir)
        yield
    finally:
        os.chdir(old_cwd)

@contextlib.contextmanager
def step(step_fn, args, target_dir):
    #step = step_fn.__name__
    state_tag = target_dir
    mkdir_p(config.state_path)
    state_file_path = os.path.join(config.state_path, state_tag)
    if not os.path.exists(state_file_path) or not os.path.exists(target_dir):
        step_fn(*args)
    with open(state_file_path, 'w'):
        pass

def untar(basename):
    if os.path.exists(basename):
        shutil.rmtree(basename)
    check_call([config.tar_path, 'xf', '%s.tar.gz' % basename])

def rename_for_vc(basename, suffix):
    suffixed_dir = '%s-%s' % (basename, suffix)
    if os.path.exists(suffixed_dir):
        shutil.rmtree(suffixed_dir)
    os.rename(basename, suffixed_dir)
    return suffixed_dir
    
def require_file_exists(path):
    if not os.path.exists(path):
        raise Exception('Path %s does not exist!' % path)
    return path

class PythonRelease(str):
    @property
    def dotless(self):
        return self.replace('.', '')

class PythonVersion(str):
    @property
    def release(self):
        return PythonRelease('.'.join(self.split('.')[:2]))

class PythonBinary(object):
    def __init__(self, python_release, bitness):
        self.python_release = python_release
        self.bitness = bitness

    @property
    def executable_path(self):
        return config.python_path_template % dict(
            python_release=self.python_release.dotless,
            bitness=self.bitness)

class Batch(object):
    def __init__(self, bc):
        self.bc = bc
        self.commands = []
        
        self.add(self.vcvars_cmd)
        self.add('echo on')
        if self.bc.vc_version == 'vc14':
            # I don't know why vcvars doesn't configure this under vc14
            windows_sdk_path = 'c:\\program files (x86)\\microsoft sdks\\windows\\v7.1a'
            self.add('set include=%s\\include;%%include%%' % windows_sdk_path)
            if self.bc.bitness == 32:
                self.add('set lib=%s\\lib;%%lib%%' % windows_sdk_path)
                self.add('set path=%s\\bin;%%path%%' % windows_sdk_path)
            else:
                self.add('set lib=%s\\lib\\x64;%%lib%%' % windows_sdk_path)
                self.add('set path=%s\\bin\\x64;%%path%%' % windows_sdk_path)
        self.add(self.nasm_cmd)
        
    def add(self, cmd):
        self.commands.append(cmd)
        
    # if patch fails to apply hunks, it exits with nonzero code.
    # if patch doesn't find the patch file to apply, it exits with a zero code!
    ERROR_CHECK = 'IF %ERRORLEVEL% NEQ 0 exit %errorlevel%'

    def batch_text(self):
        return ("\n" + self.ERROR_CHECK + "\n").join(self.commands)

    @property
    def vcvars_bitness_parameter(self):
        params = {
            32: 'x86',
            64: 'amd64',
        }
        return params[self.bc.bitness]

    @property
    def vcvars_relative_path(self):
        return 'vc/vcvarsall.bat'

    @property
    def vc_path(self):
        if self.bc.vc_version in config.vc_paths and config.vc_paths[self.bc.vc_version]:
            path = config.vc_paths[self.bc.vc_version]
            if not os.path.join(path, self.vcvars_relative_path):
                raise Exception('vcvars not found in specified path')
            return path
        else:
            for path in config.default_vc_paths[self.bc.vc_version]:
                if os.path.exists(os.path.join(path, self.vcvars_relative_path)):
                    return path
            raise Exception('No usable vc path found')

    @property
    def vcvars_path(self):
        return os.path.join(self.vc_path, self.vcvars_relative_path)

    @property
    def vcvars_cmd(self):
        # https://msdn.microsoft.com/en-us/library/x4d2c09s.aspx
        return "call \"%s\" %s" % (
            self.vcvars_path,
            self.vcvars_bitness_parameter,
        )

    @property
    def nasm_cmd(self):
        return "set path=%s;%%path%%\n" % config.nasm_path

class BuildConfig(ExtendedConfig):
    '''Parameters for a particular build configuration.
    
    Unlike ExtendedConfig, this class fixes bitness and Python version.
    '''
    
    def __init__(self, **kwargs):
        ExtendedConfig.__init__(self, **kwargs)
        for k in kwargs:
            setattr(self, k, kwargs[k])

class Builder(object):
    def __init__(self, **kwargs):
        bitness = kwargs.pop('bitness')
        assert bitness in (32, 64)
        self.bitness = bitness
        self.vc_version = kwargs.pop('vc_version')
        self.config = kwargs.pop('config')
        self.use_dlls = False

    @contextlib.contextmanager
    def execute_batch(self):
        batch = Batch(BuildConfig(vc_version=self.vc_version, bitness=self.bitness))
        yield batch
        with open('doit.bat', 'w') as f:
            f.write(batch.batch_text())
        if False:
            print("Executing:")
            with open('doit.bat', 'r') as f:
                print(f.read())
            sys.stdout.flush()
        rv = subprocess.call(['doit.bat'])
        if rv != 0:
            print("\nFailed to execute the following commands:\n")
            with open('doit.bat', 'r') as f:
                print(f.read())
            sys.stdout.flush()
            exit(3)

    @property
    def vc_tag(self):
        return '%s-%s' % (self.vc_version, self.bitness)

class StandardBuilder(Builder):
    @property
    def state_tag(self):
        return self.output_dir_path

    @property
    def bin_path(self):
        return os.path.join(config.archives_path, self.output_dir_path, 'dist', 'bin')

    @property
    def include_path(self):
        return os.path.join(config.archives_path, self.output_dir_path, 'dist', 'include')

    @property
    def lib_path(self):
        return os.path.join(config.archives_path, self.output_dir_path, 'dist', 'lib')

    @property
    def dll_paths(self):
        raise NotImplementedError

class ZlibBuilder(StandardBuilder):
    def build(self):
        fetch('http://downloads.sourceforge.net/project/libpng/zlib/%s/zlib-%s.tar.gz' % (self.config.zlib_version, self.config.zlib_version))
        untar('zlib-%s' % self.config.zlib_version)
        zlib_dir = rename_for_vc('zlib-%s' % self.config.zlib_version, self.vc_tag)
        with in_dir(zlib_dir):
            with self.execute_batch() as b:
                b.add("nmake /f win32/Makefile.msc")
                # libcurl loves its _a suffixes on static library names
                b.add("cp zlib.lib zlib_a.lib")
                
                # assemble dist
                b.add('mkdir dist dist\\include dist\\lib dist\\bin')
                b.add('cp *.lib *.exp dist/lib')
                b.add('cp *.dll dist/bin')
                b.add('cp *.h dist/include')

    @property
    def output_dir_path(self):
        return 'zlib-%s-%s' % (self.config.zlib_version, self.vc_tag)

    @property
    def dll_paths(self):
        return [
            os.path.join(self.bin_path, 'zlib1.dll'),
        ]

class OpensslBuilder(StandardBuilder):
    def build(self):
        fetch('https://www.openssl.org/source/openssl-%s.tar.gz' % self.config.openssl_version)
        try:
            untar('openssl-%s' % self.config.openssl_version)
        except subprocess.CalledProcessError:
            # openssl tarballs include symlinks which cannot be extracted on windows,
            # and hence cause errors during extraction.
            # apparently these symlinks will be regenerated at configure stage...
            # makes one wonder why they are included in the first place.
            pass
        # another openssl gem:
        # nasm output is redirected to NUL which ends up creating a file named NUL.
        # however being a reserved file name this file is not deletable by
        # ordinary tools.
        nul_file = "openssl-%s-%s\\NUL" % (self.config.openssl_version, self.vc_tag)
        check_call(['rm', '-f', nul_file])
        openssl_dir = rename_for_vc('openssl-%s' % self.config.openssl_version, self.vc_tag)
        with in_dir(openssl_dir):
            with self.execute_batch() as b:
                if self.config.openssl_version_tuple < (1, 1):
                    # openssl 1.0.2
                    b.add("patch -p0 < %s" % 
                        require_file_exists(os.path.join(config.winbuild_patch_root, 'openssl-fix-crt-1.0.2.patch')))
                else:
                    # openssl 1.1.0
                    b.add("patch -p0 < %s" %
                        require_file_exists(os.path.join(config.winbuild_patch_root, 'openssl-fix-crt-1.1.0.patch')))
                if self.bitness == 64:
                    target = 'VC-WIN64A'
                    batch_file = 'do_win64a'
                else:
                    target = 'VC-WIN32'
                    batch_file = 'do_nasm'

                # msysgit perl has trouble with backslashes used in
                # win64 assembly things in openssl 1.0.2
                # and in x86 assembly as well in openssl 1.1.0;
                # use ActiveState Perl
                if not os.path.exists(config.activestate_perl_bin_path):
                    raise ValueError('activestate_perl_bin_path refers to a nonexisting path')
                if not os.path.exists(os.path.join(config.activestate_perl_bin_path, 'perl.exe')):
                    raise ValueError('No perl binary in activestate_perl_bin_path')
                b.add("set path=%s;%%path%%" % config.activestate_perl_bin_path)
                b.add("perl -v")

                openssl_prefix = os.path.join(os.path.realpath('.'), 'build')
                # Do not want compression:
                # https://en.wikipedia.org/wiki/CRIME
                extras = ['no-comp']
                if config.openssl_version_tuple >= (1, 1):
                    # openssl 1.1.0
                    # in 1.1.0 the static/shared selection is handled by
                    # invoking the right makefile
                    extras += ['no-shared']
                    
                    # looks like openssl 1.1.0c does not derive
                    # --openssldir from --prefix, like its Configure claims,
                    # and like 1.0.2 does; provide a relative openssl dir
                    # manually
                    extras += ['--openssldir=ssl']
                b.add("perl Configure %s %s --prefix=%s" % (target, ' '.join(extras), openssl_prefix))
                
                if config.openssl_version_tuple < (1, 1):
                    # openssl 1.0.2
                    b.add("call ms\\%s" % batch_file)
                    b.add("nmake -f ms\\nt.mak")
                    b.add("nmake -f ms\\nt.mak install")
                else:
                    # openssl 1.1.0
                    b.add("nmake")
                    b.add("nmake install")
                
                # assemble dist
                b.add('mkdir dist')
                b.add('cp -r build/include build/lib dist')

    @property
    def output_dir_path(self):
        return 'openssl-%s-%s' % (self.config.openssl_version, self.vc_tag)

class CaresBuilder(StandardBuilder):
    def build(self):
        fetch('http://c-ares.haxx.se/download/c-ares-%s.tar.gz' % (self.config.cares_version))
        untar('c-ares-%s' % self.config.cares_version)
        if self.config.cares_version == '1.12.0':
            # msvc_ver.inc is missing in c-ares-1.12.0.tar.gz
            # https://github.com/c-ares/c-ares/issues/69
            fetch('https://raw.githubusercontent.com/c-ares/c-ares/cares-1_12_0/msvc_ver.inc',
                  archive='c-ares-1.12.0/msvc_ver.inc')
        cares_dir = rename_for_vc('c-ares-%s' % self.config.cares_version, self.vc_tag)
        with in_dir(cares_dir):
            with self.execute_batch() as b:
                if self.config.cares_version == '1.10.0':
                    b.add("patch -p1 < %s" %
                        require_file_exists(os.path.join(config.winbuild_patch_root, 'c-ares-vs2015.patch')))
                b.add("nmake -f Makefile.msvc")
                
                # assemble dist
                b.add('mkdir dist dist\\include dist\\lib')
                if self.config.cares_version_tuple < (1, 14, 0):
                    subdir = 'ms%s0' % self.vc_version
                else:
                    subdir = 'msvc'
                b.add('cp %s/cares/lib-release/*.lib dist/lib' % subdir)
                b.add('cp *.h dist/include')

    @property
    def output_dir_path(self):
        return 'c-ares-%s-%s' % (self.config.cares_version, self.vc_tag)

class Libssh2Builder(StandardBuilder):
    def build(self):
        fetch('http://www.libssh2.org/download/libssh2-%s.tar.gz' % (self.config.libssh2_version))
        untar('libssh2-%s' % self.config.libssh2_version)
        libssh2_dir = rename_for_vc('libssh2-%s' % self.config.libssh2_version, self.vc_tag)
        with in_dir(libssh2_dir):
            with self.execute_batch() as b:
                if self.config.libssh2_version_tuple < (1, 8, 0) and self.vc_version == 'vc14':
                    b.add("patch -p0 < %s" %
                        require_file_exists(os.path.join(config.winbuild_patch_root, 'libssh2-vs2015.patch')))
                zlib_builder = ZlibBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                openssl_builder = OpensslBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                vars = '''
OPENSSLINC=%(openssl_include_path)s
OPENSSLLIB=%(openssl_lib_path)s
ZLIBINC=%(zlib_include_path)s
ZLIBLIB=%(zlib_lib_path)s
WITH_ZLIB=1
BUILD_STATIC_LIB=1
                ''' % dict(
                    openssl_include_path=openssl_builder.include_path,
                    openssl_lib_path=openssl_builder.lib_path,
                    zlib_include_path=zlib_builder.include_path,
                    zlib_lib_path=zlib_builder.lib_path,
                )
                with open('win32/config.mk', 'r+') as cf:
                    contents = cf.read()
                    cf.seek(0)
                    cf.write(vars)
                    cf.write(contents)
                b.add("nmake -f NMakefile")
                # libcurl loves its _a suffixes on static library names
                b.add("cp Release\\src\\libssh2.lib Release\\src\\libssh2_a.lib")
                
                # assemble dist
                b.add('mkdir dist dist\\include dist\\lib')
                b.add('cp Release/src/*.lib dist/lib')
                b.add('cp -r include dist')

    @property
    def output_dir_path(self):
        return 'libssh2-%s-%s' % (self.config.libssh2_version, self.vc_tag)

class Nghttp2Builder(StandardBuilder):
    CMAKE_GENERATORS = {
        # Thanks cmake for requiring both version number and year,
        # necessitating this additional map
        'vc9': 'Visual Studio 9 2008',
        'vc14': 'Visual Studio 14 2015',
    }
    
    def build(self):
        fetch('https://github.com/nghttp2/nghttp2/releases/download/v%s/nghttp2-%s.tar.gz' % (self.config.nghttp2_version, self.config.nghttp2_version))
        untar('nghttp2-%s' % self.config.nghttp2_version)
        nghttp2_dir = rename_for_vc('nghttp2-%s' % self.config.nghttp2_version, self.vc_tag)
                
        # nghttp2 uses stdint.h which msvc9 does not ship.
        # Amazingly, nghttp2 can seemingly build successfully without this
        # file existing, but libcurl build subsequently fails
        # when it tries to include stdint.h.
        # Well, the reason why nghttp2 builds correctly is because it is built
        # with the wrong compiler - msvc14 when 9 and 14 are both installed.
        # nghttp2 build with msvc9 does fail without stdint.h existing.
        if self.vc_version == 'vc9':
            # https://stackoverflow.com/questions/126279/c99-stdint-h-header-and-ms-visual-studio
            fetch('https://raw.githubusercontent.com/mattn/gntp-send/master/include/msinttypes/stdint.h')
            with in_dir(nghttp2_dir):
                shutil.copy('../stdint.h', 'lib/includes/stdint.h')
        
        assert config.use_zlib
        zlib_builder = ZlibBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
        assert config.use_openssl
        openssl_builder = OpensslBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
        assert config.use_cares
        cares_builder = CaresBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
        with in_dir(nghttp2_dir):
            with self.execute_batch() as b:
                cmd = ' '.join([
                    '"%s"' % config.cmake_path,
                    # I don't know if this does anything, build type/config
                    # must be specified with --build option below.
                    '-DCMAKE_BUILD_TYPE=Release',
                    # This configures libnghttp2 only which is what we want.
                    # However, configure step still complains about all of the
                    # missing dependencies for nghttp2 server.
                    # And there is no indication whatsoever from configure step
                    # that this option is enabled, or that the missing
                    # dependency complaints can be ignored.
                    '-DENABLE_LIB_ONLY=1',
                    # This is required to get a static library built.
                    # However, even with this turned on there is still a DLL
                    # built - without an import library for it.
                    '-DENABLE_STATIC_LIB=1',
                    # And cmake ignores all visual studio environment variables
                    # and uses the newest compiler by default, which is great
                    # if one doesn't care what compiler their code is compiled with.
                    '-G', '"%s"' % self.CMAKE_GENERATORS[self.vc_version],
                ])
                b.add('%s .' % cmd)
                # --config Release here is what produces a release build
                b.add('"%s" --build . --config Release' % config.cmake_path)
                
                # libcurl and its library name expectations
                b.add('cp lib/Release/nghttp2.lib lib/Release/nghttp2_static.lib')
                
                # assemble dist
                b.add('mkdir dist dist\\include dist\\include\\nghttp2 dist\\lib')
                b.add('cp lib/Release/*.lib dist/lib')
                b.add('cp lib/includes/nghttp2/*.h dist/include/nghttp2')
                # stdint.h
                b.add('cp lib/includes/*.h dist/include')

    @property
    def output_dir_path(self):
        return 'nghttp2-%s-%s' % (self.config.nghttp2_version, self.vc_tag)

class LibcurlBuilder(StandardBuilder):
    def build(self):
        fetch('https://curl.haxx.se/download/curl-%s.tar.gz' % self.config.libcurl_version)
        untar('curl-%s' % self.config.libcurl_version)
        curl_dir = rename_for_vc('curl-%s' % self.config.libcurl_version, self.vc_tag)
        with in_dir(os.path.join(curl_dir, 'winbuild')):
            with self.execute_batch() as b:
                b.add("patch -p1 < %s" %
                    require_file_exists(os.path.join(config.winbuild_patch_root, 'libcurl-fix-zlib-references.patch')))
                if self.use_dlls:
                    dll_or_static = 'dll'
                else:
                    dll_or_static = 'static'
                extra_options = ' mode=%s' % dll_or_static
                if self.config.use_zlib:
                    zlib_builder = ZlibBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                    b.add("set include=%%include%%;%s" % zlib_builder.include_path)
                    b.add("set lib=%%lib%%;%s" % zlib_builder.lib_path)
                    extra_options += ' WITH_ZLIB=%s' % dll_or_static
                if self.config.use_openssl:
                    openssl_builder = OpensslBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                    b.add("set include=%%include%%;%s" % openssl_builder.include_path)
                    b.add("set lib=%%lib%%;%s" % openssl_builder.lib_path)
                    extra_options += ' WITH_SSL=%s' % dll_or_static
                if self.config.use_cares:
                    cares_builder = CaresBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                    b.add("set include=%%include%%;%s" % cares_builder.include_path)
                    b.add("set lib=%%lib%%;%s" % cares_builder.lib_path)
                    extra_options += ' WITH_CARES=%s' % dll_or_static
                if self.config.use_libssh2:
                    libssh2_builder = Libssh2Builder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                    b.add("set include=%%include%%;%s" % libssh2_builder.include_path)
                    b.add("set lib=%%lib%%;%s" % libssh2_builder.lib_path)
                    extra_options += ' WITH_SSH2=%s' % dll_or_static
                if self.config.use_nghttp2:
                    nghttp2_builder = Nghttp2Builder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                    b.add("set include=%%include%%;%s" % nghttp2_builder.include_path)
                    b.add("set lib=%%lib%%;%s" % nghttp2_builder.lib_path)
                    extra_options += ' WITH_NGHTTP2=%s' % dll_or_static
                if config.openssl_version_tuple >= (1, 1):
                    # openssl 1.1.0
                    # https://curl.haxx.se/mail/lib-2016-08/0104.html
                    # https://github.com/curl/curl/issues/984
                    # crypt32.lib: http://stackoverflow.com/questions/37522654/linking-with-openssl-lib-statically
                    extra_options += ' MAKE="NMAKE /e" SSL_LIBS="libssl.lib libcrypto.lib crypt32.lib"'
                b.add("nmake /f Makefile.vc ENABLE_IDN=no%s" % extra_options)
        
        # assemble dist - figure out where libcurl put its files
        # and move them to a more reasonable location
        with in_dir(curl_dir):
            subdirs = sorted(os.listdir('builds'))
            if len(subdirs) != 3:
                raise Exception('Should be 3 directories here')
            expected_dir = subdirs.pop(0)
            for dir in subdirs:
                if not dir.startswith(expected_dir):
                    raise Exception('%s does not start with %s' % (dir, expected_dir))
                    
            os.rename(os.path.join('builds', expected_dir), 'dist')

    @property
    def output_dir_path(self):
        return 'curl-%s-%s' % (self.config.libcurl_version, self.vc_tag)

    @property
    def dll_paths(self):
        return [
            os.path.join(self.bin_path, 'libcurl.dll'),
        ]

class PycurlBuilder(Builder):
    def __init__(self, **kwargs):
        self.python_release = kwargs.pop('python_release')
        kwargs['vc_version'] = PYTHON_VC_VERSIONS[self.python_release]
        super(PycurlBuilder, self).__init__(**kwargs)

    @property
    def python_path(self):
        if config.build_wheels:
            python_path = os.path.join(config.archives_path, 'venv-%s-%s' % (self.python_release, self.bitness), 'scripts', 'python')
        else:
            python_path = PythonBinary(self.python_release, self.bitness).executable_path
        return python_path

    @property
    def platform_indicator(self):
        platform_indicators = {32: 'win32', 64: 'win-amd64'}
        return platform_indicators[self.bitness]

    def build(self, targets):
        libcurl_builder = LibcurlBuilder(bitness=self.bitness,
            vc_version=self.vc_version,
            config=self.config)
        libcurl_dir = os.path.join(os.path.abspath(libcurl_builder.output_dir_path), 'dist')
        dll_paths = libcurl_builder.dll_paths
        if self.config.use_zlib:
            zlib_builder = ZlibBuilder(bitness=self.bitness,
                vc_version=self.vc_version,
                config=self.config,
            )
            dll_paths += zlib_builder.dll_paths
        dll_paths = [os.path.abspath(dll_path) for dll_path in dll_paths]
        with in_dir(os.path.join('pycurl-%s' % self.config.pycurl_version)):
            dest_lib_path = 'build/lib.%s-%s' % (self.platform_indicator,
                self.python_release)
            # exists for building additional targets for the same python version
            mkdir_p(dest_lib_path)
            if self.use_dlls:
                for dll_path in dll_paths:
                    shutil.copy(dll_path, dest_lib_path)
            with self.execute_batch() as b:
                b.add("%s setup.py docstrings" % (self.python_path,))
                if self.use_dlls:
                    libcurl_arg = '--use-libcurl-dll'
                else:
                    libcurl_arg = '--libcurl-lib-name=libcurl_a.lib'
                if self.config.use_openssl:
                    libcurl_arg += ' --with-openssl'
                    if config.openssl_version_tuple >= (1, 1):
                        libcurl_arg += ' --openssl-lib-name=""'
                    openssl_builder = OpensslBuilder(bitness=self.bitness, vc_version=self.vc_version, config=self.config)
                    b.add("set include=%%include%%;%s" % openssl_builder.include_path)
                    b.add("set lib=%%lib%%;%s" % openssl_builder.lib_path)
                #if build_wheels:
                    #b.add("call %s" % os.path.join('..', 'venv-%s-%s' % (self.python_release, self.bitness), 'Scripts', 'activate'))
                if config.build_wheels:
                    targets = targets + ['bdist_wheel']
                b.add("%s setup.py %s --curl-dir=%s %s" % (
                    self.python_path, ' '.join(targets), libcurl_dir, libcurl_arg))
            if 'bdist' in targets:
                zip_basename_orig = 'pycurl-%s.%s.zip' % (
                    self.config.pycurl_version, self.platform_indicator)
                zip_basename_new = 'pycurl-%s.%s-py%s.zip' % (
                    self.config.pycurl_version, self.platform_indicator, self.python_release)
                with zipfile.ZipFile('dist/%s' % zip_basename_orig, 'r') as src_zip:
                    with zipfile.ZipFile('dist/%s' % zip_basename_new, 'w') as dest_zip:
                        for name in src_zip.namelist():
                            parts = name.split('/')
                            while True:
                                popped = parts.pop(0)
                                if popped == 'python%s' % self.python_release.dotless or popped.startswith('venv-'):
                                    break
                            assert len(parts) > 0
                            new_name = '/'.join(parts)
                            print('Recompressing %s -> %s' % (name, new_name))

                            member = src_zip.open(name)
                            dest_zip.writestr(new_name, member.read(), zipfile.ZIP_DEFLATED)

BITNESSES = (32, 64)

def build_dependencies(config):
    if config.use_libssh2:
        if not config.use_zlib:
            # technically we can build libssh2 without zlib but I don't want to bother
            raise ValueError('use_zlib must be True if use_libssh2 is True')
        if not config.use_openssl:
            raise ValueError('use_openssl must be True if use_libssh2 is True')

    if config.git_bin_path:
        os.environ['PATH'] += ";%s" % config.git_bin_path
    mkdir_p(config.archives_path)
    with in_dir(config.archives_path):
        for bitness in config.bitnesses:
            for vc_version in needed_vc_versions(config.python_versions):
                if opts.verbose:
                    print('Builddep for %s, %s-bit' % (vc_version, bitness))
                if config.use_zlib:
                    zlib_builder = ZlibBuilder(bitness=bitness, vc_version=vc_version, config=config)
                    step(zlib_builder.build, (), zlib_builder.state_tag)
                if config.use_openssl:
                    openssl_builder = OpensslBuilder(bitness=bitness, vc_version=vc_version, config=config)
                    step(openssl_builder.build, (), openssl_builder.state_tag)
                if config.use_cares:
                    cares_builder = CaresBuilder(bitness=bitness, vc_version=vc_version, config=config)
                    step(cares_builder.build, (), cares_builder.state_tag)
                if config.use_libssh2:
                    libssh2_builder = Libssh2Builder(bitness=bitness, vc_version=vc_version, config=config)
                    step(libssh2_builder.build, (), libssh2_builder.state_tag)
                if config.use_nghttp2:
                    nghttp2_builder = Nghttp2Builder(bitness=bitness, vc_version=vc_version, config=config)
                    step(nghttp2_builder.build, (), nghttp2_builder.state_tag)
                libcurl_builder = LibcurlBuilder(bitness=bitness, vc_version=vc_version,
                    config=config)
                step(libcurl_builder.build, (), libcurl_builder.state_tag)

def build(config):
    # note: adds git_bin_path to PATH if necessary, and creates archives_path
    build_dependencies(config)
    with in_dir(config.archives_path):
        def prepare_pycurl():
            #fetch('https://dl.bintray.com/pycurl/pycurl/pycurl-%s.tar.gz' % pycurl_version)
            if os.path.exists('pycurl-%s' % config.pycurl_version):
                # shutil.rmtree is incapable of removing .git directory because it contains
                # files marked read-only (tested on python 2.7 and 3.6)
                #shutil.rmtree('pycurl-%s' % config.pycurl_version)
                check_call([config.rm_path, '-rf', 'pycurl-%s' % config.pycurl_version])
            #check_call([tar_path, 'xf', 'pycurl-%s.tar.gz' % pycurl_version])
            shutil.copytree('c:/dev/pycurl', 'pycurl-%s' % config.pycurl_version)
            if config.build_wheels:
                with in_dir('pycurl-%s' % config.pycurl_version):
                    check_call([config.sed_path, '-i',
                        's/from distutils.core import setup/from setuptools import setup/',
                        'setup.py'])

        prepare_pycurl()

        for bitness in config.bitnesses:
            for python_release in config.python_releases:
                targets = ['bdist', 'bdist_wininst', 'bdist_msi']
                vc_version = PYTHON_VC_VERSIONS[python_release]
                builder = PycurlBuilder(bitness=bitness, vc_version=vc_version,
                    python_release=python_release, config=config)
                builder.build(targets)

def python_metas():
    metas = []
    for version in config.python_versions:
        parts = [int(part) for part in version.split('.')]
        if parts[0] >= 3 and parts[1] >= 5:
            ext = 'exe'
            amd64_suffix = '-amd64'
        else:
            ext = 'msi'
            amd64_suffix = '.amd64'
        url_32 = 'https://www.python.org/ftp/python/%s/python-%s.%s' % (version, version, ext)
        url_64 = 'https://www.python.org/ftp/python/%s/python-%s%s.%s' % (version, version, amd64_suffix, ext)
        meta = dict(
            version=version, ext=ext, amd64_suffix=amd64_suffix,
            url_32=url_32, url_64=url_64,
            installed_path_32 = 'c:\\dev\\32\\python%d%d' % (parts[0], parts[1]),
            installed_path_64 = 'c:\\dev\\64\\python%d%d' % (parts[0], parts[1]),
        )
        metas.append(meta)
    return metas

def download_pythons(config):
    for meta in python_metas():
        for bitness in config.bitnesses:
            fetch_to_archives(meta['url_%d' % bitness])

def install_pythons(config):
    for meta in python_metas():
        for bitness in config.bitnesses:
            if not os.path.exists(meta['installed_path_%d' % bitness]):
                install_python(config, meta, bitness)

def fix_slashes(path):
    return path.replace('/', '\\')

# http://eddiejackson.net/wp/?p=10276
def install_python(config, meta, bitness):
    archive_path = fix_slashes(os.path.join(config.archives_path, os.path.basename(meta['url_%d' % bitness])))
    if meta['ext'] == 'exe':
        cmd = [archive_path]
    else:
        cmd = ['msiexec', '/i', archive_path, '/norestart']
    cmd += ['/passive', 'InstallAllUsers=1',
            'Include_test=0', 'Include_doc=0', 'Include_launcher=0',
            'Include_ckltk=0',
            'TargetDir=%s' % meta['installed_path_%d' % bitness],
        ]
    sys.stdout.write('Installing python %s (%d bit)\n' % (meta['version'], bitness))
    print(' '.join(cmd))
    sys.stdout.flush()
    check_call(cmd)

def download_bootstrap_python(config):
    version = config.python_versions[-2]
    url = 'https://www.python.org/ftp/python/%s/python-%s.msi' % (version, version)
    fetch(url)

def install_virtualenv(config):
    with in_dir(config.archives_path):
        #fetch('https://pypi.python.org/packages/source/v/virtualenv/virtualenv-%s.tar.gz' % virtualenv_version)
        fetch('https://pypi.python.org/packages/d4/0c/9840c08189e030873387a73b90ada981885010dd9aea134d6de30cd24cb8/virtualenv-15.1.0.tar.gz')
        for bitness in config.bitnesses:
            for python_release in config.python_releases:
                print('Installing virtualenv %s for Python %s (%s bit)' % (config.virtualenv_version, python_release, bitness))
                sys.stdout.flush()
                untar('virtualenv-%s' % config.virtualenv_version)
                with in_dir('virtualenv-%s' % config.virtualenv_version):
                    python_binary = PythonBinary(python_release, bitness)
                    cmd = [python_binary.executable_path, 'setup.py', 'install']
                    check_call(cmd)

def create_virtualenvs(config):
    for bitness in config.bitnesses:
        for python_release in config.python_releases:
            print('Creating a virtualenv for Python %s (%s bit)' % (python_release, bitness))
            sys.stdout.flush()
            with in_dir(config.archives_path):
                python_binary = PythonBinary(python_release, bitness)
                venv_basename = 'venv-%s-%s' % (python_release, bitness)
                cmd = [python_binary.executable_path, '-m', 'virtualenv', venv_basename]
                check_call(cmd)

import optparse

parser = optparse.OptionParser()
parser.add_option('-b', '--bitness', help='Bitnesses build for, comma separated')
parser.add_option('-p', '--python', help='Python versions to build for, comma separated')
parser.add_option('-v', '--verbose', help='Print what is being done', action='store_true')
opts, args = parser.parse_args()

if opts.bitness:
    chosen_bitnesses = [int(bitness) for bitness in opts.bitness.split(',')]
    for bitness in chosen_bitnesses:
        if bitness not in BITNESSES:
            print('Invalid bitness %d' % bitness)
            exit(2)
else:
    chosen_bitnesses = BITNESSES

if opts.python:
    chosen_pythons = opts.python.split(',')
    chosen_python_versions = []
    for python in chosen_pythons:
        python = python.replace('.', '')
        python = python[0] + '.' + python[1] + '.'
        ok = False
        for python_version in Config.python_versions:
            if python_version.startswith(python):
                chosen_python_versions.append(python_version)
                ok = True
        if not ok:
            print('Invalid python %s' % python)
            exit(2)
else:
    chosen_python_versions = Config.python_versions

config = ExtendedConfig(
    bitnesses=chosen_bitnesses,
    python_versions=chosen_python_versions,
)

if len(args) > 0:
    if args[0] == 'download':
        download_pythons(config)
    elif args[0] == 'bootstrap':
        download_bootstrap_python(config)
    elif args[0] == 'installpy':
        install_pythons(config)
    elif args[0] == 'builddeps':
        build_dependencies(config)
    elif args[0] == 'installvirtualenv':
        install_virtualenv(config)
    elif args[0] == 'createvirtualenvs':
        create_virtualenvs(config)
    else:
        print('Unknown command: %s' % args[0])
        exit(2)
else:
    build(config)
