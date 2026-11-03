#!/usr/bin/env python3
"""Package Nano builds without running or flashing a device."""
import hashlib
import os
import re
import runpy
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLUGIN_API=int(re.search(r"^#define PLUGIN_API_VERSION\s+(\d+)$",
                        (ROOT/"rockbox-firmware/apps/plugin.h").read_text(),
                        re.M).group(1))
THEMES=runpy.run_path(str(ROOT/"scripts/generate-podthings-logo.py"))["THEMES"]
sys.path.insert(0, str(ROOT/"scripts"))
from installer_config import config as installer_metadata, firmware_archive, release_payload
VERSION=os.environ.get("PODTHINGS_VERSION",(ROOT/"VERSION").read_text().strip())
BUILDS=ROOT/"generated-artifacts/rockbox"
OUTPUT=ROOT/"generated-artifacts/releases"
TOOLS=ROOT/".local/rockbox-toolchain/bin"
EXPERIMENTAL=os.environ.get("PODTHINGS_NANO_UNVALIDATED_WRITES","0")=="1"
MKDFU=ROOT/"rockbox-firmware/utils/mks5lboot/mks5lboot"


def arm_elf(path):
    data=path.read_bytes()
    if data[:6]!=b"\x7fELF\x01\x01" or struct.unpack_from("<H",data,18)[0]!=40:
        raise ValueError(f"Not a little-endian ARM ELF: {path}")
    # Firmware credit lettering is rasterized into the logo; its footer is text.
    branding=(b"PodThing OS - %s - Based on Rockbox"
              if path.name=="rockbox.elf" else b"Built by abrendan")
    if VERSION.encode() not in data or branding not in data:
        raise ValueError(f"Wrong version/branding: {path}")


def write_archive(path,files):
    manifest="".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                     for name,data in files.items()).encode()
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as archive:
        for name,data in files.items():
            archive.writestr(name,data)
        archive.writestr("SHA256SUMS",manifest)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip(): raise ValueError("Archive CRC failure")
    print(path.relative_to(ROOT))

def make_dfu(*args):
    subprocess.run([str(MKDFU),*map(str,args)],check=True,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def verify_experimental_policy(elf):
    symbols=subprocess.check_output([str(TOOLS/"arm-elf-eabi-nm"),"-S",str(elf)]).decode()
    table=re.search(r"^[0-9a-f]+\s+([0-9a-f]+)\s+\w\s+nand_chip_table$",symbols,re.MULTILINE)
    # Eighteen Apple ID/bank rows, each a 16-byte ARM struct.
    if not table or int(table[1],16)!=18*16:
        raise ValueError(f"Experimental build lacks the complete recognized chip table: {elf}")
    names=re.findall(r"^[0-9a-f]+\s+[0-9a-f]+\s+\w\s+(nand_geometry_writes_allowed\S*)$",
                     symbols,re.MULTILINE)
    if not names:
        raise ValueError(f"Missing independently inspectable NAND write policy: {elf}")
    for name in set(names):
        instructions=subprocess.check_output([
            str(TOOLS/"arm-elf-eabi-objdump"),"-d",f"--disassemble={name}",str(elf)]).decode()
        opcodes=re.findall(r"^\s*[0-9a-f]+:\s+([0-9a-f]{8})\s",instructions,re.MULTILINE)
        # The header policy may have one local copy in each storage TU.
        if (not opcodes or len(opcodes)%2 or
            any(opcodes[i:i+2]!=["e3a00001","e12fff1e"]
                for i in range(0,len(opcodes),2))):
            raise ValueError(f"Experimental write policy is not enabled: {elf}: {name}")

def artwork_stack_report(elf):
    """Check the ARM entry frames, not a host compiler's much larger stack."""
    report=[]
    for name,limit in (("podthings_itunes_art",2048),("pa_fingerprint",256)):
        text=subprocess.check_output([
            str(TOOLS/"arm-elf-eabi-objdump"),"-d",f"--disassemble={name}",str(elf)]).decode()
        marker=f"<{name}>:"
        if marker not in text:
            if name=="pa_fingerprint":
                report.append(f"{name}: inlined (included in caller frame)")
                continue
            raise ValueError("Missing artwork entry point")
        instructions=[line for line in text.split(marker,1)[1].splitlines()
                      if re.match(r"\s*[0-9a-f]+:\s+[0-9a-f]{8}\s",line)]
        frame=0
        for line in instructions[:10]:
            opcode=re.match(r"\s*[0-9a-f]+:\s+([0-9a-f]{8})",line)[1]
            if opcode.startswith("e92d"):  # ARM push register mask
                frame+=bin(int(opcode[4:],16)).count("1")*4
            allocation=re.search(r"\bsub\s+sp, sp, #(\d+)",line)
            if allocation:
                frame+=int(allocation[1])
        if not 0<frame<=limit:
            raise ValueError(f"Artwork ARM entry frame exceeds budget: {name}: {frame}/{limit}")
        report.append(f"{name}: {frame} bytes (entry-frame budget {limit})")
    report.append("Entry frames are not a bound on total nested/indirect call-stack usage.")
    report.append("The audio thread stack is unchanged; physical playback still needs confirmation.")
    return ("\n".join(report)+"\n").encode()


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    suffix="-experimental-writes" if EXPERIMENTAL else ""
    fw=BUILDS/("ipodnano3g-firmware"+suffix)
    boot=BUILDS/("ipodnano3g-bootloader"+suffix)
    check=BUILDS/"ipodnano3g-nandcheck"
    for folder,image in ((fw,"rockbox.elf"),(boot,"bootloader.elf"),(check,"bootloader.elf")):
        arm_elf(folder/image)
    if EXPERIMENTAL:
        for folder,image in ((fw,"rockbox.elf"),(boot,"bootloader.elf")):
            verify_experimental_policy(folder/image)
        if b"Experimental NAND writes" in (boot/"bootloader.elf").read_bytes():
            raise ValueError("Obsolete on-device bootloader label")
        stack_report=artwork_stack_report(fw/"rockbox.elf")
    symbols=subprocess.check_output([str(TOOLS/"arm-elf-eabi-nm"),str(check/"bootloader.elf")]).decode()
    if "nand_check_init" not in symbols:
        raise ValueError("Diagnostic was not built with NAND_CHECK")
    normal_symbols=subprocess.check_output([str(TOOLS/"arm-elf-eabi-nm"),str(boot/"bootloader.elf")]).decode()
    if "nand_check_init" in normal_symbols:
        raise ValueError("Diagnostic and normal bootloaders were mixed up")
    instructions=subprocess.check_output([
        str(TOOLS/"arm-elf-eabi-objdump"),"-d","--disassemble=nand_write_sectors",
        str(check/"bootloader.elf")]).decode()
    # The actual diagnostic entry point must be the unconditional error stub.
    opcodes=re.findall(r"^\s*[0-9a-f]+:\s+([0-9a-f]{8})\s",instructions,re.MULTILINE)
    if opcodes!=["e3e00000","e12fff1e"]:
        raise ValueError("Inspect diagnostic write rejection before packaging")
    dfu=check/"podthings-nano3g-readonly.dfu"
    make_dfu("--mkdfu-raw",check/"bootloader.bin",dfu)
    dfu_bytes=dfu.read_bytes()
    # This is an Apple boot-ROM payload, not a generic USB-DFU-suffix file.
    # Reconstruct it offline to establish that it contains this exact loader.
    with tempfile.TemporaryDirectory() as directory:
        rebuilt=Path(directory)/"check.dfu"
        make_dfu("--mkdfu-raw",check/"bootloader.bin",rebuilt)
        if rebuilt.read_bytes()!=dfu_bytes:
            raise ValueError("DFU does not match the verified read-only loader")
    for folder in (boot,):
        if (folder/"bootloader-ipodnano3g.ipod").read_bytes()[4:8]!=b"nn3g":
            raise ValueError("Wrong bootloader model")
    firmware=fw/"podthingsos-firmware.zip"
    with zipfile.ZipFile(firmware) as archive:
        if archive.testzip(): raise ValueError("Firmware ZIP CRC failure")
        if archive.read(".podthingsloader/podthingsos.ipod")[4:8]!=b"nn3g":
            raise ValueError("Wrong firmware model")
        plugins=[n for n in archive.namelist() if n.endswith(".rock")]
        if not plugins: raise ValueError("Missing plugins")
        for name in plugins:
            if struct.unpack_from("<HH",archive.read(name),4)!=(117,PLUGIN_API):
                raise ValueError(f"Wrong model/API plugin: {name}")
        for variant in THEMES:
            for suffix in (".wps",".sbs","/branding.bmp","/seek-dot.bmp"):
                archive.getinfo(f".podthingsloader/wps/podthingsos-{variant}{suffix}")
            skin=archive.read(f".podthingsloader/wps/podthingsos-{variant}.wps")
            for asset in (ROOT/f"rockbox-firmware/wps/podthingsos-{variant}").glob("*.bmp"):
                if asset.name.startswith("photo-"):
                    continue  # Photo's 220x176-only assets are not Nano resources.
                archive.getinfo(f".podthingsloader/wps/podthingsos-{variant}/{asset.name}")
            if b"%?pN<%Vd(P)%Vd(L)|%Vd(I)>" not in skin or b"\niPod\n" not in skin:
                raise ValueError("Missing Nano unbranded iPod fallback")
    files={
        "installer.config":installer_metadata("diagnostic",VERSION,"ipodnano3g"),
        "COPYING":(ROOT/"rockbox-firmware/docs/COPYING").read_bytes(),
        "diagnostic/podthings-nano3g-readonly.dfu":dfu_bytes,
        "diagnostic/nandcheck.py":(ROOT/"rockbox-firmware/utils/ipodnano3g/nandcheck/nandcheck.py").read_bytes(),
    }
    source_module=runpy.run_path(str(ROOT/"scripts/package-podthings-release.py"))
    source=source_module["source_package"](VERSION)
    # Publish matching GPL source separately, never inside installable kits.
    if EXPERIMENTAL:
        with tempfile.TemporaryDirectory() as directory:
            installer=Path(directory)/"install.dfu"
            uninstaller=Path(directory)/"uninstall.dfu"
            # These are Nano-specific dualboot NOR payloads. Never --single.
            make_dfu("--mkdfu-inst",boot/"bootloader-ipodnano3g.ipod",installer)
            make_dfu("--mkdfu-uninst","ipodnano3g",uninstaller)
            update_bytes=firmware_archive(firmware.read_bytes(),VERSION,"ipodnano3g")
            files.update({
                "installer.config":installer_metadata("device-kit",VERSION,"ipodnano3g"),
                "firmware/podthingsos-firmware.zip":update_bytes,
                "bootloader/bootloader-ipodnano3g.ipod":(boot/"bootloader-ipodnano3g.ipod").read_bytes(),
                "bootloader/install-nano3g-dualboot.dfu":installer.read_bytes(),
                "bootloader/uninstall-nano3g-dualboot.dfu":uninstaller.read_bytes(),
                "NANO-STORAGE-NOTES.txt":(
                    "Safety notice: Nano installation writes boot flash and NAND.\n"
                    "Not all recognized NAND variants have been physically validated.\n"
                    "Data loss and a full restore are possible.\n").encode(),
            })
        write_archive(OUTPUT/f"PodThings-OS-ipodnano3g-{VERSION}.zip",release_payload(files))
        update=OUTPUT/f"PodThings-OS-ipodnano3g-{VERSION}-firmware-update.zip"
        update.write_bytes(update_bytes)
        print(update.relative_to(ROOT))
        return
    write_archive(OUTPUT/f"PodThings-OS-Nano3G-ReadOnly-Check-{VERSION}.zip",release_payload(files))
    files.update({
        "DO-NOT-INSTALL-YET/podthingsos-firmware.zip":firmware.read_bytes(),
        "DO-NOT-INSTALL-YET/bootloader-ipodnano3g.ipod":(boot/"bootloader-ipodnano3g.ipod").read_bytes(),
    })
    write_archive(OUTPUT/f"PodThings-OS-ipodnano3g-{VERSION}.zip",release_payload(files))


if __name__=="__main__":
    main()
