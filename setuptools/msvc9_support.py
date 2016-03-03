"""
This module improve support for Microsoft Visual C++ compilers. (Windows Only)
"""
import os
import itertools
import distutils.errors
import winreg

try:
    # Distutil file for MSVC++ 9.0 and upper
    import distutils.msvc9compiler as msvc9compiler
except ImportError:
    pass

try:
    # Distutil file for MSVC++ 14.0 and upper
    import distutils._msvccompiler as msvc14compiler
except ImportError:
    pass


import six

unpatched = dict()


def patch_for_specialized_compiler():
    """
    Patch functions in distutils to use standalone Microsoft Visual C++
    compilers.

    Known supported compilers:
    --------------------------
    Microsoft Visual C++ 9.0:
        Microsoft Visual C++ Compiler for Python 2.7 (x86, amd64);
        Microsoft Windows SDK 7.0 (x86, x64, ia64);
        Microsoft Windows SDK 6.1 (x86, x64, ia64)

    Microsoft Visual C++ 10.0:
        Microsoft Windows SDK 7.1 (x86, x64, ia64)

    Microsoft Visual C++ 14.0:
        Microsoft Visual C++ Build Tools 2015 (x86, x64, arm)
    """
    if 'distutils' not in globals():
        # The module isn't available to be patched
        return

    if unpatched:
        # Already patched
        return

    try:
        # Patch distutils.msvc9compiler
        unpatched['msvc9_find_vcvarsall'] = msvc9compiler.find_vcvarsall
        msvc9compiler.find_vcvarsall = msvc9_find_vcvarsall
        unpatched['msvc9_query_vcvarsall'] = msvc9compiler.query_vcvarsall
        msvc9compiler.query_vcvarsall = msvc9_query_vcvarsall
    except:
        pass

    try:
        # Patch distutils._msvccompiler._get_vc_env
        unpatched['msv14_get_vc_env'] = msvc14compiler._get_vc_env
        msvc14compiler._get_vc_env = msvc14_get_vc_env
    except:
        pass


def msvc9_find_vcvarsall(version):
    """
    Patched "distutils.msvc9compiler.find_vcvarsall" to use the standalone
    compiler build for Python (VCForPython). Fall back to original behavior
    when the standalone compiler is not available.

    Known supported compilers
    -------------------------
    Microsoft Visual C++ 9.0:
        Microsoft Visual C++ Compiler for Python 2.7 (x86, amd64)

    Parameters
    ----------
    version: float
        Required Microsoft Visual C++ version.

    Return
    ------
    vcvarsall.bat path: str
    """
    Reg = msvc9compiler.Reg
    VC_BASE = r'Software\%sMicrosoft\DevDiv\VCForPython\%0.1f'
    key = VC_BASE % ('', version)
    try:
        # Per-user installs register the compiler path here
        productdir = Reg.get_value(key, "installdir")
    except KeyError:
        try:
            # All-user installs on a 64-bit system register here
            key = VC_BASE % ('Wow6432Node\\', version)
            productdir = Reg.get_value(key, "installdir")
        except KeyError:
            productdir = None

    if productdir:
        vcvarsall = os.path.os.path.join(productdir, "vcvarsall.bat")
        if os.path.isfile(vcvarsall):
            return vcvarsall

    return unpatched['msvc9_find_vcvarsall'](version)


def msvc9_query_vcvarsall(ver, arch='x86', *args, **kwargs):
    """
    Patched "distutils.msvc9compiler.query_vcvarsall" for support standalones
    compilers.

    Known supported compilers
    -------------------------
    Microsoft Visual C++ 9.0:
        Microsoft Visual C++ Compiler for Python 2.7 (x86, amd64);
        Microsoft Windows SDK 7.0 (x86, x64, ia64);
        Microsoft Windows SDK 6.1 (x86, x64, ia64)

    Microsoft Visual C++ 10.0:
        Microsoft Windows SDK 7.1 (x86, x64, ia64)

    Parameters
    ----------
    ver: float
        Required Microsoft Visual C++ version.
    arch: str
        Target architecture.

    Return
    ------
    environment: dict
    """
    # Try to get environement from vcvarsall.bat (Classical way)
    try:
        return unpatched['msvc9_query_vcvarsall'](ver, arch, *args, **kwargs)
    except distutils.errors.DistutilsPlatformError:
        # Pass error if Vcvarsall.bat is missing
        pass
    except ValueError:
        # Pass error if environment not set after executing vcvarsall.bat
        pass

    # If error, try to set environment directly
    try:
        return EnvironmentInfo(arch, ver).return_env()
    except distutils.errors.DistutilsPlatformError as exc:
        _augment_exception(exc, ver, arch)
        raise


def msvc14_get_vc_env(plat_spec):
    """
    Patched "distutils._msvccompiler._get_vc_env" for support standalones
    compilers.

    Known supported compilers
    -------------------------
    Microsoft Visual C++ 14.0:
        Microsoft Visual C++ Build Tools 2015 (x86, x64, arm)

    Parameters
    ----------
    plat_spec: str
        Target architecture.

    Return
    ------
    environment: dict
    """
    # Try to get environement from vcvarsall.bat (Classical way)
    try:
        return unpatched['msv14_get_vc_env'](plat_spec)
    except distutils.errors.DistutilsPlatformError:
        # Pass error Vcvarsall.bat is missing
        pass

    # If error, try to set environment directly
    try:
        return EnvironmentInfo(plat_spec, vcvermin=14.0).return_env()
    except distutils.errors.DistutilsPlatformError as exc:
        _augment_exception(exc, 14.0)
        raise


def _augment_exception(exc, version, arch=''):
    """
    Add details to the exception message to help guide the user
    as to what action will resolve it.
    """
    # Error if MSVC++ directory not found or environment not set
    message = exc.args[0]

    if "vcvarsall" in message.lower() or "visual c" in message.lower():
        # Special error message if MSVC++ not installed
        message = 'Microsoft Visual C++ %0.1f is required (%s).' %\
            (version, message)
        msdownload = r'www.microsoft.com/download/details.aspx?id=%d'
        if version == 9.0:
            if arch.lower().find('ia64') > -1:
                # For VC++ 9.0, if IA64 support is needed, redirect user
                # to Windows SDK 7.0
                message += ' Get it with "Microsoft Windows SDK 7.0": '
                message += msdownload % 3138
            else:
                # For VC++ 9.0 redirect user to Vc++ for Python 2.7 :
                # This redirection link is maintained by Microsoft.
                # Contact vspython@microsoft.com if it needs updating.
                message += r' Get it from http://aka.ms/vcpython27'
        elif version == 10.0:
            # For VC++ 10.0 Redirect user to Windows SDK 7.1
            message += ' Get it with "Microsoft Windows SDK 7.1": '
            message += msdownload % 8279

    exc.args[0] = message


class PlatformInfo:
    """
    Current and Target Architectures informations.

    Parameters
    ----------
    arch: str
        Target architecture.
    """
    current_cpu = os.environ['processor_architecture'].lower()

    def __init__(self, arch):
        self.arch = arch.lower()

    @property
    def target_cpu(self):
        return self.arch[self.arch.find('_') + 1:]

    def target_is_x86(self):
        return self.target_cpu == 'x86'

    def current_is_x86(self):
        return self.current_cpu == 'x86'

    def current_dir(self, hidex86=False, x64=False):
        """
        Current platform specific subfolder.

        Parameters
        ----------
        hidex86: bool
            return '' and not '\x86' if architecture is x86.
        x64: bool
            return '\x64' and not '\amd64' if architecture is amd64.

        Return
        ------
        subfolder: str
            "\target"
        """
        return (
            '' if (self.current_cpu == 'x86' and hidex86) else
            r'\x64' if (self.current_cpu == 'amd64' and x64) else
            r'\%s' % self.current_cpu
        )

    def target_dir(self, hidex86=False, x64=False):
        """
        Target platform specific subfolder.

        Parameters
        ----------
        hidex86: bool
            return '' and not '\x86' if architecture is x86.
        x64: bool
            return '\x64' and not '\amd64' if architecture is amd64.

        Return
        ------
        subfolder: str
            "\current"
        """
        return (
            '' if (self.target_cpu == 'x86' and hidex86) else
            r'\x64' if (self.target_cpu == 'amd64' and x64) else
            r'\%s' % self.target_cpu
        )

    def cross_dir(self, forcex86=False):
        """
        Cross platform specific subfolder.

        Parameters
        ----------
        forcex86: bool
            If cross compilation, return 'x86' as current architecture even
            if current acritecture is not x86.

        Return
        ------
        subfolder: str
            "\current" if target architecture is current architecture,
            "\current_target" if not.
        """
        path = self.target_dir(True)
        if self.target_cpu != self.current_cpu:
            current = 'x86' if forcex86 else self.current_cpu
            path = path.replace('\\', '\\%s_' % current)
        return path


class RegistryInfo:
    """
    Microsoft Visual Studio related registry informations.

    Parameters
    ----------
    platform_info: PlatformInfo
        "PlatformInfo" instance.
    """
    HKEYS = (winreg.HKEY_USERS,
             winreg.HKEY_CURRENT_USER,
             winreg.HKEY_LOCAL_MACHINE,
             winreg.HKEY_CLASSES_ROOT)

    def __init__(self, platform_info):
        self.pi = platform_info

    @property
    def microsoft(self):
        """
        Microsoft software registry key.
        """
        return os.path.join(
            'Software',
            '' if self.pi.current_is_x86() else 'Wow6432Node',
            'Microsoft',
        )

    @property
    def sxs(self):
        """
        Microsoft Visual Studio SxS registry key.
        """
        return os.path.join(self.microsoft, r'VisualStudio\SxS')

    @property
    def vc(self):
        """
        Microsoft Visual C++ registry key.
        """
        return os.path.join(self.sxs, 'VC7')

    @property
    def vs(self):
        """
        Microsoft Visual Studio registry key.
        """
        return os.path.join(self.sxs, 'VS7')

    @property
    def vc_for_python(self):
        """
        Microsoft Visual C++ for Python registry key.
        """
        path = r'DevDiv\VCForPython'
        return os.path.join(self.microsoft, path)

    @property
    def windows_sdk(self):
        """
        Microsoft Windows/Platform SDK registry key.
        """
        return os.path.join(self.microsoft, r'Microsoft SDKs\Windows')

    def lookup(self, key, name):
        """
        Look for values in registry.

        Parameters
        ----------
        key: str
            Registry key path where look.
        name: str
            Value name to find.

        Return
        ------
        str: value
        """
        for hkey in self.HKEYS:
            try:
                bkey = winreg.OpenKey(hkey, key, 0, winreg.KEY_READ)
            except FileNotFoundError:
                continue
            try:
                return winreg.QueryValueEx(bkey, name)[0]
            except FileNotFoundError:
                pass


class SystemInfo:
    """
    Microsoft Windows and Visual Studio related system inormations.

    Parameters
    ----------
    registry_info: RegistryInfo
        "RegistryInfo" instance.
    vcver: float
        Required Microsoft Visual C++ version.
    """
    WinDir = os.environ['WinDir']
    ProgramFiles = os.environ['ProgramFiles']
    ProgramFilesx86 = os.environ.get('ProgramFiles(x86)', ProgramFiles)

    def __init__(self, registry_info, vcver=None):
        self.ri = registry_info
        if vcver:
            self.vcver = vcver
        else:
            try:
                self.vcver = self.find_availables_vcver()[-1]
            except IndexError:
                err = 'No Microsoft Visual C++ version found'
                raise distutils.errors.DistutilsPlatformError(err)

    def find_availables_vcver(self):
        """
        Find all availables Microsoft Visual C++ versions.
        """
        vckeys = (self.ri.vc, self.ri.vc_for_python)
        vsvers = []
        for hkey in self.ri.HKEYS:
            for key in vckeys:
                try:
                    bkey = winreg.OpenKey(hkey, key, 0, winreg.KEY_READ)
                except FileNotFoundError:
                    continue
                subkeys, values, _ = winreg.QueryInfoKey(bkey)
                for i in range(values):
                    try:
                        ver = float(winreg.EnumValue(bkey, i)[0])
                        if ver not in vsvers:
                            vsvers.append(ver)
                    except ValueError:
                        pass
                for i in range(subkeys):
                    try:
                        ver = float(winreg.EnumKey(bkey, i))
                        if ver not in vsvers:
                            vsvers.append(ver)
                    except ValueError:
                        pass
        return sorted(vsvers)

    @property
    def VSInstallDir(self):
        """
        Microsoft Visual Studio directory.
        """
        # Default path
        name = 'Microsoft Visual Studio %0.1f' % self.vcver
        default = os.path.join(self.ProgramFilesx86, name)

        # Try to get path from registry, if fail use default path
        return self.ri.lookup(self.ri.vs, '%0.1f' % self.vcver) or default

    @property
    def VCInstallDir(self):
        """
        Microsoft Visual C++ directory.
        """
        # Default path
        default = r'Microsoft Visual Studio %0.1f\VC' % self.vcver
        guess_vc = os.path.join(self.ProgramFilesx86, default)

        # Try to get "VC++ for Python" path from registry as default path
        path = os.path.join(self.ri.vc_for_python, '%0.1f' % self.vcver)
        python_vc = self.ri.lookup(path, 'installdir')
        default_vc = os.path.join(python_vc, 'VC') if python_vc else guess_vc

        # Try to get path from registry, if fail use default path
        result = self.ri.lookup(self.ri.vc, '%0.1f' % self.vcver) or default_vc

        if not os.path.isdir(result):
            msg = 'Microsoft Visual C++ directory not found'
            raise distutils.errors.DistutilsPlatformError(msg)

        return result

    @property
    def WindowsSdkDir(self):
        """
        Microsoft Windows SDK directory.
        """
        sdkdir = ''
        if self.vcver == 9.0:
            sdkver = ('7.0', '6.1', '6.0a')
        elif self.vcver == 10.0:
            sdkver = ('7.1', '7.0a')
        elif self.vcver == 14.0:
            sdkver = ('10.0', '8.1', '8.1a')
        else:
            sdkver = ()
        for ver in sdkver:
            # Try to get it from registry
            loc = os.path.join(self.ri.windows_sdk, 'v%s' % ver)
            sdkdir = self.ri.lookup(loc, 'installationfolder')
            if sdkdir:
                break
        if not sdkdir or not os.path.isdir(sdkdir):
            # Try to get "VC++ for Python" version from registry
            path = os.path.join(self.ri.vc_for_python, '%0.1f' % self.vcver)
            install_base = self.ri.lookup(path, 'installdir')
            if install_base:
                sdkdir = os.path.join(install_base, 'WinSDK')
        if not sdkdir or not os.path.isdir(sdkdir):
            # If fail, use default new path
            for ver in sdkver:
                intver = ver[:ver.rfind('.')]
                path = r'Microsoft SDKs\Windows Kits\%s' % (intver)
                d = os.path.join(self.ProgramFiles, path)
                if os.path.isdir(d):
                    sdkdir = d
        if not sdkdir or not os.path.isdir(sdkdir):
            # If fail, use default old path
            for ver in sdkver:
                path = r'Microsoft SDKs\Windows\v%s' % ver
                d = os.path.join(self.ProgramFiles, path)
                if os.path.isdir(d):
                    sdkdir = d
        if not sdkdir:
            # If fail, use Platform SDK
            sdkdir = os.path.join(self.VCInstallDir, 'PlatformSDK')
        return sdkdir

    @property
    def FrameworkDir32(self):
        """
        Microsoft .NET Framework 32bit directory.
        """
        # Default path
        guess_fw = os.path.join(self.WinDir, r'Microsoft.NET\Framework')

        # Try to get path from registry, if fail use default path
        return self.ri.lookup(self.ri.vc, 'frameworkdir32') or guess_fw

    @property
    def FrameworkDir64(self):
        """
        Microsoft .NET Framework 64bit directory.
        """
        # Default path
        guess_fw = os.path.join(self.WinDir, r'Microsoft.NET\Framework64')

        # Try to get path from registry, if fail use default path
        return self.ri.lookup(self.ri.vc, 'frameworkdir64') or guess_fw

    @property
    def FrameworkVersion32(self):
        """
        Microsoft .NET Framework 32bit versions.
        """
        return self._find_dot_net_versions(32)

    @property
    def FrameworkVersion64(self):
        """
        Microsoft .NET Framework 64bit versions.
        """
        return self._find_dot_net_versions(64)

    def _find_dot_net_versions(self, bits=32):
        """
        Find Microsoft .NET Framework versions.

        Parameters
        ----------
        bits: int
            Platform number of bits: 32 or 64.
        """
        # Find actual .NET version
        ver = self.ri.lookup(self.ri.vc, 'frameworkver%d' % bits) or ''

        # Set .NET versions for specified MSVC++ version
        if self.vcver >= 14.0:
            frameworkver = (ver, 'v4.0')
        elif self.vcver == 10.0:
            if ver.lower()[:2] != 'v4':
                ver = ''
            ver = ver or 'v4.0.30319'
            frameworkver = (ver, 'v3.5')
        elif self.vcver == 9.0:
            frameworkver = ('v3.5', 'v2.0.50727')
        elif self.vcver == 8.0:
            frameworkver = ('v3.0', 'v2.0.50727')
        return frameworkver


class EnvironmentInfo:
    """
    Return environment variables for specified Microsoft Visual C++ version
    and platform : Lib, Include, Path and libpath.

    This function is compatible with Microsoft Visual C++ 9.0 to 14.0.

    Parameters
    ----------
    arch: str
        Target architecture.
    vcver: float
        Required Microsoft Visual C++ version. If not set, autodetect the last
        version.
    vcvermin: float
        Minimum Microsoft Visual C++ version.
    """
    def __init__(self, arch, vcver=None, vcvermin=None):
        self.pi = PlatformInfo(arch)
        self.ri = RegistryInfo(self.pi)
        self.si = SystemInfo(self.ri, vcver)

        if self.vcver < vcvermin:
            err = 'No suitable Microsoft Visual C++ version found'
            raise distutils.errors.DistutilsPlatformError(err)

    @property
    def vcver(self):
        """
        Microsoft Visual C++ version.
        """
        return self.si.vcver

    @property
    def VSTools(self):
        """
        Microsoft Visual Studio Tools
        """
        paths = [r'Common7\IDE', r'Common7\Tools']
        if self.vcver >= 14.0:
            arch_subdir = self.pi.current_dir(hidex86=True, x64=True)
            paths += [r'Common7\IDE\CommonExtensions\Microsoft\TestWindow']
            paths += [r'Team Tools\Performance Tools']
            paths += [r'Team Tools\Performance Tools%s' % arch_subdir]
        return [os.path.join(self.si.VSInstallDir, path) for path in paths]

    @property
    def VCIncludes(self):
        """
        Microsoft Visual C++ & Microsoft Foundation Class Includes
        """
        return [os.path.join(self.si.VCInstallDir, 'Include'),
                os.path.join(self.si.VCInstallDir, 'ATLMFC\Include')]

    @property
    def VCLibraries(self):
        """
        Microsoft Visual C++ & Microsoft Foundation Class Libraries
        """
        arch_subdir = self.pi.target_dir(hidex86=True)
        paths = ['Lib%s' % arch_subdir, r'ATLMFC\Lib%s' % arch_subdir]
        if self.vcver >= 14.0:
            paths += [r'Lib\store%s' % arch_subdir]
        return [os.path.join(self.si.VCInstallDir, path) for path in paths]

    @property
    def VCStoreRefs(self):
        """
        Microsoft Visual C++ store references Libraries
        """
        path = os.path.join(self.si.VCInstallDir, r'Lib\store\references')
        return [path] if self.vcver >= 14.0 else []

    @property
    def VCTools(self):
        """
        Microsoft Visual C++ Tools
        """
        forcex86 = True if self.vcver <= 10.0 else False
        arch_subdir = self.pi.cross_dir(forcex86)
        tools = [
            os.path.join(self.si.VCInstallDir, 'VCPackages'),
            os.path.join(self.si.VCInstallDir, 'Bin%s' % arch_subdir),
        ]
        if self.pi.cross_dir() and self.vcver >= 14.0:
            path = 'Bin%s' % self.pi.current_dir(hidex86=True)
            tools += [os.path.join(self.si.VCInstallDir, path)]
        else:
            tools += [os.path.join(self.si.VCInstallDir, 'Bin')]
        return tools

    @property
    def OSLibraries(self):
        """
        Microsoft Windows SDK Libraries
        """
        arch_subdir = self.pi.target_dir(hidex86=True, x64=True)
        return [os.path.join(self.si.WindowsSdkDir, 'Bin%s' % arch_subdir)]

    @property
    def OSIncludes(self):
        """
        Microsoft Windows SDK Include
        """
        return [
            os.path.join(self.si.WindowsSdkDir, 'Include'),
            os.path.join(self.si.WindowsSdkDir, r'Include\gl'),
        ]

    @property
    def SdkTools(self):
        """
        Microsoft Windows SDK Tools
        """
        if self.vcver <= 10:
            arch_subdir = self.pi.target_dir(hidex86=True, x64=True)
        else:
            arch_subdir = self.pi.target_dir(x64=True)
        tools = [os.path.join(self.si.WindowsSdkDir, 'Bin')]
        if not self.pi.target_is_x86():
            path = 'Bin%s' % arch_subdir
            tools += [os.path.join(self.si.WindowsSdkDir, path)]
        if self.vcver == 10.0:
            path = r'Bin\NETFX 4.0 Tools%s' % arch_subdir
            tools += [os.path.join(self.si.WindowsSdkDir, path)]
        return tools

    @property
    def SdkSetup(self):
        """
        Microsoft Windows SDK Setup
        """
        return [os.path.join(self.si.WindowsSdkDir, 'Setup')]

    @property
    def FxTools(self):
        """
        Microsoft .NET Framework Tools
        """
        pi = self.pi
        si = self.si
        if self.vcver <= 10.0:
            include32 = True
            include64 = not pi.target_is_x86() and not pi.current_is_x86()
        else:
            include32 = pi.target_is_x86() or pi.current_is_x86()
            include64 = pi.current_cpu == 'amd64' or pi.target_cpu == 'amd64'
        tools = []
        if include32:
            tools += [
                os.path.join(si.FrameworkDir32, ver)
                for ver in si.FrameworkVersion32
            ]
        if include64:
            tools += [
                os.path.join(si.FrameworkDir64, ver)
                for ver in si.FrameworkVersion64
            ]
        return tools

    @property
    def VsTDb(self):
        """
        Microsoft Visual Studio Team System Database
        """
        return [os.path.join(self.si.VSInstallDir, r'VSTSDB\Deploy')]

    @property
    def MSBuild(self):
        """
        Microsoft Build Engine
        """
        arch_subdir = self.pi.current_dir(hidex86=True)
        path = r'\MSBuild\%0.1f\bin%s' % (self.vcver, arch_subdir)
        return [
            os.path.join(self.si.ProgramFilesx86, path),
            os.path.join(self.si.ProgramFiles, path)
        ]

    @property
    def HTMLWs(self):
        """
        Microsoft HTML Help Workshop
        """
        return [
            os.path.join(self.si.ProgramFilesx86, 'HTML Help Workshop'),
            os.path.join(self.si.ProgramFiles, 'HTML Help Workshop')
        ]

    @property
    def VCRuntimeRedist(self):
        """
        Microsoft Visual C++ runtime redistribuable dll
        """
        arch_subdir = self.pi.target_dir(x64=True)
        vcruntime = 'redist%s\\Microsoft.VC%d0.CRT\\vcruntime%d0.dll'
        vcruntime = vcruntime % (arch_subdir, self.vcver, self.vcver)
        return os.path.join(self.si.VCInstallDir, vcruntime)

    def return_env(self):
        """
        Return environment dict.
        """
        env = dict(
            include=self._build_paths('include',
                                      [self.VCIncludes,
                                       self.OSIncludes]),
            lib=self._build_paths('lib',
                                  [self.VCLibraries,
                                   self.OSLibraries,
                                   self.FxTools]),
            libpath=self._build_paths('libpath',
                                      [self.VCLibraries,
                                       self.FxTools,
                                       self.VCStoreRefs]),
            path=self._build_paths('path',
                                   [self.VCTools,
                                    self.VSTools,
                                    self.VsTDb,
                                    self.SdkTools,
                                    self.SdkSetup,
                                    self.FxTools,
                                    self.MSBuild,
                                    self.HTMLWs]),
        )
        if self.vcver >= 14 and os.path.isfile(self.VCRuntimeRedist):
            env['py_vcruntime_redist'] = self.VCRuntimeRedist
        return env

    def _build_paths(self, name, spec_path_lists):
        """
        Given an environment variable name and specified paths,
        return a pathsep-separated string of paths containing
        unique, extant, directories from those paths and from
        the environment variable. Raise an error if no paths
        are resolved.
        """
        # flatten spec_path_lists
        spec_paths = itertools.chain.from_iterable(spec_path_lists)
        env_paths = os.environ.get(name, '').split(os.pathsep)
        paths = itertools.chain(spec_paths, env_paths)
        extant_paths = list(filter(os.path.isdir, paths))
        if not extant_paths:
            msg = "%s environment variable is empty" % name.upper()
            raise distutils.errors.DistutilsPlatformError(msg)
        unique_paths = self._unique_everseen(extant_paths)
        return os.pathsep.join(unique_paths)

    # from Python docs
    def _unique_everseen(self, iterable, key=None):
        """
        List unique elements, preserving order.
        Remember all elements ever seen.
        """
        # unique_everseen('AAAABBBCCDAABBB') --> A B C D
        # unique_everseen('ABBCcAD', str.lower) --> A B C D
        seen = set()
        seen_add = seen.add
        filterfalse = six.moves.filterfalse
        if key is None:
            for element in filterfalse(seen.__contains__, iterable):
                seen_add(element)
                yield element
        else:
            for element in iterable:
                k = key(element)
                if k not in seen:
                    seen_add(k)
                    yield element
