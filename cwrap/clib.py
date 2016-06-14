#  Copyright (C) 2016 Statoil ASA, Norway.
#
#  This file is part of cwrap.
#
#  cwrap is free software: you can redistribute it and/or modify it under the
#  terms of the GNU General Public License as published by the Free Software
#  Foundation, either version 3 of the License, or (at your option) any later
#  version.
#
#  cwrap is distributed in the hope that it will be useful, but WITHOUT ANY
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
#  A PARTICULAR PURPOSE.
#
#  See the GNU General Public License at <http://www.gnu.org/licenses/gpl.html>
#  for more details.

"""Convenience module for loading shared library.

Observe that to ensure that all libraries are loaded through the same
code path, all required libraries should be loaded explicitly through
the use of import statements; i.e. the ert.geo package requires the
libert_util librarary, to ensure that the correct version of the
libert_util.so library file is loaded we should manually load that
first as:

   import ert.util
   GEO_LIB = clib.ert_load("libert_geometry")

Otherwise the standard operating system dependency resolve code will
be invoked when loading libert_geometry, and that could in principle
lead to loading a different version of libert_util.so
"""

import platform
import ctypes
import os
from ctypes.util import find_library

so_extension = {"linux"  : "so",
                "linux2" : "so",
                "linux3" : "so",
                "win32"  : "dll",
                "win64"  : "dll",
                "darwin" : "dylib" }


_PATHS = ["/usr/local/lib", "/usr/local/lib64", "/usr/lib", "/usr/lib64",
          "/lib64", "/lib/x86_64-linux-gnu/", "/usr/lib/x86_64-linux-gnu/",
          "/lib", ".", "..", "~/lib", os.path.dirname(os.path.abspath(__file__)),
          os.getcwd()]
_SUFFIX = [""]
_SUFFIX += [".%d" % d for d in range(10)]
_SUFFIX += ["%d" % d for d in range(10)]


# The variables ert_lib_path and ert_so_version will be set by the build
# system. The system works like this:
#
#  1. There is a CMake configure command which creates a module
#     __ert_lib_info.py; that module has the two elements
#     'ert_lib_path' and 'ert_so_version' which are inferred by the
#     build system.
#
#  2. The root package ert/__init__py will try to import thel
#     __ert_lib_info module; if that import succeeds the attributes
#     ert_lib_path and ert_so_version OF THIS MODULE will be updated.
#
#     If the import fails this module will continue with the default
#     values. The default values will work if the shared libraries are
#     in the default library load path, with unversioned named/links.


ert_lib_path = None           # Warning: Will be updated from ert/__init__.py
ert_so_version = ""           #




# Passing None to the CDLL() function means to open a lib handle to
# the current runnning process, i.e. like dlopen( NULL ). We must
# special case this to avoid creating the bogus argument 'None.so'.

def lib_name(lib , path = None , so_version = ""):
    if lib is None:
        return None
    if len(lib) > 2 and lib[-3:] == ".so":
        lib = lib[:-3] # strip away .so ending, add it later anyway

    platform_key = platform.system().lower()

    if platform_key == "darwin":
        so_name = "%s%s.%s" % (lib, so_version, so_extension[ platform_key ])
    else:
        so_name = "%s.%s%s" % (lib, so_extension[ platform_key ], so_version)

    if path:
        abs_lib = os.path.join( path , so_name )
        ret_lib = __try_import(abs_lib)
        if ret_lib:
            return ret_lib
    return _find_library(so_name)


def _find_library(lib):
    global _PATHS, _SUFFIX
    ctypes_find = find_library(lib) # does this ever work?
    if ctypes_find and __try_import(ctypes_find):
        print "A miracle.  ctypes found it!"
        return ctypes_find
    for p in _PATHS:
        for s in _SUFFIX:
            abs_path = os.path.join( p , lib + s)
            ret_lib = __try_import( abs_path )
            if ret_lib:
                return ret_lib

    # paniccy attempt
    from sys import argv
    f1 = os.path.join(os.path.abspath(__file__), argv[0])
    f2 = os.path.join(os.getcwd(), argv[0])
    last_attempt = __try_import(os.path.join(os.path.dirname(f1), lib))
    if last_attempt:
        return last_attempt
    last_attempt = __try_import(os.path.join(os.path.dirname(f2), lib))
    if last_attempt:
        return last_attempt
    print "failed to find", lib, "in", _PATHS
    return None


def __try_import( abs_path ) :
    if not os.path.isfile(abs_path):
        return None
    try:
        lib = ctypes.CDLL( abs_path , ctypes.RTLD_GLOBAL )
        return abs_path
    except OSError as ose:
        print "OSError", ose, abs_path
        s = __load_gnu_ld_script( abs_path )
        if s:
            print "GNU LD script:",s
            print "ignoring ... "
        return None
    except ImportError as ie:
        print "ImportError", ie, abs_path
        return None
    except Exception as e:
        print "Exception", e, abs_path
        return None


def __load_gnu_ld_script( src ):
    if not (os.path.isfile(src)):
        return set()
    import mimetypes

    ret = set()

    if mimetypes.guess_type(src)[0] != 'text/plain':
        return ret

    with open(src, "r") as f:
        for l in f:
            l = l.split()
            for x in l:
                if len(x) > 3 and x[0] == '/':
                    if os.path.isfile(x):
                        ret.add(x)
    return ret



def __load( lib_list, ert_prefix):
    """
    Thin wrapper around the ctypes.CDLL function for loading shared library.

    The shared libraries typically exist under several different
    names, with different level of version detail. Unfortunately the
    same library can exist under different names on different
    computers, to support this the load function can get several
    arguments like:

       load("libz.so" , "libz.so.1" , "libz.so.1.2.1.2" , "libZ-fucker.so")

    Will return a handle to the first successfull load, and raise
    ImportError if none of the loads succeed.
    """

    error_list = {}
    dll = None
    for lib in lib_list:
        if ert_prefix:
            lib_file = lib_name( lib , path = ert_lib_path , so_version = ert_so_version)
        else:
            lib_file = lib_name( lib , so_version = ert_so_version)

        try:
            dll = ctypes.CDLL(lib_file , ctypes.RTLD_GLOBAL)
            return dll
        except Exception, exc:
            error_list[lib] = exc

    error_msg = "\nFailed to load shared library:%s\n\ndlopen() error:\n" % lib_list[0]
    for lib in error_list.keys():
        error_msg += "   %16s : %s\n" % (lib, error_list[lib])
    error_msg += "\n"

    LD_LIBRARY_PATH = os.getenv("LD_LIBRARY_PATH")
    if not LD_LIBRARY_PATH:
        LD_LIBRARY_PATH = ""

    error_msg += """
The runtime linker has searched through the default location of shared
libraries, and also the locations mentioned in your LD_LIBRARY_PATH
variable. Your current LD_LIBRARY_PATH setting is:

   LD_LIBRARY_PATH: %s

You might need to update this variable?
""" % LD_LIBRARY_PATH
    raise ImportError(error_msg)

#################################################################


def load( *lib_list ):
    """
    Will try to load shared library with normal load semantics.
    """
    return __load(lib_list , False)


def ert_load( *lib_list ):
    """
    Iff the ert_lib_path module variable has been set it will try to
    load shared library from that path; if that fails the loader will
    try again without imposing any path restrictions.
    """

    if ert_lib_path:
        try:
            return __load(lib_list , True)
        except ImportError:
            # Try again - ignoring the ert_lib_path setting.
            return load(*lib_list)
    else:
        # The ert_lib_path variable has not been set; just try a normal load.
        return load(*lib_list)
