import os, sys
import platform
import shutil
import subprocess
import re

def update_version(name, rootdir):
    # Full version includes the Git commit hash
    full_version = subprocess.check_output('git describe --dirty', shell=True).strip(" \n")
    vfile = open(os.path.join(rootdir, name, "_version.py"), "w")
    vfile.write("__version__='%s'" % full_version)
    vfile.close()

    # Standardized version in form major.minor.patch-build
    p = re.compile("v?(\d+\.\d+\.\d+(-\d+)?).*")
    m = p.match(full_version)
    if m is not None:
        std_version = m.group(1)
    else:
        raise RuntimeError("Failed to parse version string %s" % full_version)

    return full_version, std_version

def get_lib_template(platform):
    if platform == "win32":
        return "bin", "%s.dll"
    elif platform == "osx":
        return "lib", "lib%s.dylib"
    else:
        return "lib", "lib%s.so"

def build_plugin(package_name, rootdir, distdir, platform):
    fsldir = os.environ.get("FSLDEVDIR", os.environ.get("FSLDIR", ""))
    print("Coping Fabber libraries from %s" % fsldir)
    print("Root dir is %s" % rootdir)
    os.makedirs(distdir)

    packagedir = os.path.join(distdir, package_name)
    shutil.copytree(os.path.join(rootdir, package_name), packagedir)
    
    # Copy Fabber shared lib
    shlib_dir, shlib_template = get_lib_template(platform)
    LIB = os.path.join(fsldir, shlib_dir, shlib_template % "fabber_models_asl")
    print("%s -> %s" % (LIB, packagedir))
    shutil.copy(LIB, packagedir)

    # Copy Python dependencies
    import oxasl
    aslmoddir = os.path.join(packagedir, "deps", "oxasl")
    aslmod_src = os.path.abspath(os.path.dirname(oxasl.__file__))
    shutil.copytree(aslmod_src, aslmoddir)
    try:
        import oxasl_ve
        aslmoddir = os.path.join(packagedir, "deps", "oxasl_ve")
        aslmod_src = os.path.abspath(os.path.dirname(oxasl_ve.__file__))
        shutil.copytree(aslmod_src, aslmoddir)
    except ImportError:
        print("Not bundling OXASL_VE - not found")

    try:
        import oxasl_deblur
        aslmoddir = os.path.join(packagedir, "deps", "oxasl_deblur")
        aslmod_src = os.path.abspath(os.path.dirname(oxasl_deblur.__file__))
        shutil.copytree(aslmod_src, aslmoddir)
    except ImportError:
        print("Not bundling OXASL_DEBLUR - not found")

    try:
        import oxasl_enable
        aslmoddir = os.path.join(packagedir, "deps", "oxasl_enable")
        aslmod_src = os.path.abspath(os.path.dirname(oxasl_enable.__file__))
        shutil.copytree(aslmod_src, aslmoddir)
    except ImportError:
        print("Not bundling OXASL_ENABLE - not found")

pkgdir = os.path.abspath(os.path.dirname(__file__))
rootdir = os.path.abspath(os.path.join(pkgdir, os.pardir))
distdir = os.path.join(rootdir, "dist")
package_name = "quantiphyse_basil"

sys.path.append(rootdir)

if sys.platform.startswith("win"):
    platform="win32"
    import create_msi
    build_platform_package = create_msi.create_msi
elif sys.platform.startswith("linux"):
    platform="linux"
    import create_deb
    build_platform_package = create_deb.create_deb
elif sys.platform.startswith("darwin"):
    platform="osx"
    import create_dmg
    build_platform_package = create_dmg.create_dmg

shutil.rmtree("%s/dist" % rootdir, ignore_errors=True)
v = update_version(package_name, rootdir)
print("Version updated to %s" % v[0])
version_str_display = version_str = v[1]
if "--snapshot" in sys.argv:
    version_str_display = "snapshot"

print("Building plugin")
build_plugin(package_name, rootdir, distdir, platform)
build_platform_package("qp-" + package_name, package_name, distdir, pkgdir, v[1], version_str_display)
