#!/usr/bin/env python3
"""
Windows-compatible IPA injector for SpinLogger.dylib.

Does the same thing as inject.sh (insert_dylib + repack) but in pure Python
so it runs on Windows. Output IPA is unsigned — LiveContainer signs ad-hoc
when the IPA is loaded into a container.

Usage:
  python inject_ipa.py <input.ipa> <SpinLogger.dylib> [--out OUTPUT.ipa]
                        [--v4-model assets/v4_model.json]
"""
from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

# ─── Mach-O constants ─────────────────────────────────────────────────────
MH_MAGIC_64     = 0xFEEDFACF
FAT_MAGIC       = 0xCAFEBABE
FAT_MAGIC_BE    = 0xBEBAFECA  # big-endian form seen on disk
LC_SEGMENT_64   = 0x19
LC_LOAD_DYLIB   = 0x0C


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def u64(data: bytes, off: int) -> int:
    return struct.unpack_from('<Q', data, off)[0]


def read_header(data: bytes) -> tuple[int, int]:
    """Return (ncmds, sizeofcmds) for a thin 64-bit Mach-O."""
    magic = u32(data, 0)
    if magic != MH_MAGIC_64:
        if magic in (FAT_MAGIC, FAT_MAGIC_BE):
            raise RuntimeError(
                "fat binary not supported yet — iOS IPAs should be thin arm64"
            )
        raise RuntimeError(f"not a 64-bit Mach-O (magic=0x{magic:08x})")
    return u32(data, 16), u32(data, 20)


def first_segment_fileoff(data: bytes) -> int:
    """Lowest fileoff among segments with filesize > 0. This is where the
    header slack ends."""
    ncmds, _ = read_header(data)
    pos = 32
    lowest = 1 << 62
    for _ in range(ncmds):
        cmd, cmdsize = u32(data, pos), u32(data, pos + 4)
        if cmd == LC_SEGMENT_64:
            # struct segment_command_64:
            #   uint32 cmd, cmdsize
            #   char   segname[16]
            #   uint64 vmaddr, vmsize, fileoff, filesize
            seg_fileoff  = u64(data, pos + 8 + 16 + 8)
            seg_filesize = u64(data, pos + 8 + 16 + 16)
            if seg_filesize > 0 and seg_fileoff < lowest:
                lowest = seg_fileoff
        pos += cmdsize
    return lowest


def iter_load_dylib(data: bytes):
    """Yield (pos, cmdsize, name) for every LC_LOAD_DYLIB."""
    ncmds, _ = read_header(data)
    pos = 32
    for _ in range(ncmds):
        cmd, cmdsize = u32(data, pos), u32(data, pos + 4)
        if cmd == LC_LOAD_DYLIB:
            name_off = u32(data, pos + 8)
            name_start = pos + name_off
            name_end = data.find(b'\x00', name_start, pos + cmdsize)
            name = data[name_start:name_end].decode('utf-8', errors='replace')
            yield (pos, cmdsize, name)
        pos += cmdsize


def remove_load_dylib(data: bytearray, target_name: str) -> int:
    """Remove every LC_LOAD_DYLIB whose path matches target_name. Returns
    count removed."""
    ncmds, sizeofcmds = read_header(bytes(data))

    # Snapshot all commands.
    commands: list[bytes] = []
    removed_count = 0
    pos = 32
    for _ in range(ncmds):
        cmd, cmdsize = u32(bytes(data), pos), u32(bytes(data), pos + 4)
        raw = bytes(data[pos:pos + cmdsize])
        drop = False
        if cmd == LC_LOAD_DYLIB:
            name_off = u32(raw, 8)
            name_end = raw.find(b'\x00', name_off)
            name = raw[name_off:name_end].decode('utf-8', errors='replace')
            if name == target_name:
                drop = True
                removed_count += 1
        if not drop:
            commands.append(raw)
        pos += cmdsize

    if removed_count == 0:
        return 0

    new_block = b''.join(commands)
    # Zero the old command region, then write new block + trailing zeros.
    data[32:32 + sizeofcmds] = b'\x00' * sizeofcmds
    data[32:32 + len(new_block)] = new_block

    new_ncmds = ncmds - removed_count
    new_sizeofcmds = len(new_block)
    struct.pack_into('<II', data, 16, new_ncmds, new_sizeofcmds)
    return removed_count


def inject_load_dylib(data: bytearray, dylib_path: str) -> None:
    """Append an LC_LOAD_DYLIB pointing to dylib_path. Uses header slack."""
    ncmds, sizeofcmds = read_header(bytes(data))

    name_bytes = dylib_path.encode('utf-8') + b'\x00'
    # dylib_command fixed fields: cmd, cmdsize, name_off, timestamp,
    #                             current_version, compatibility_version
    fixed_hdr = 24
    total = fixed_hdr + len(name_bytes)
    padded = (total + 7) & ~7  # 8-byte align

    new_cmd = struct.pack(
        '<IIIIII',
        LC_LOAD_DYLIB,
        padded,
        fixed_hdr,        # name starts right after fixed fields
        2,                # timestamp
        0x00010000,       # current_version = 1.0.0
        0x00010000,       # compat_version  = 1.0.0
    ) + name_bytes + b'\x00' * (padded - total)

    header_end = 32 + sizeofcmds
    slack_end  = first_segment_fileoff(bytes(data))
    available  = slack_end - header_end
    if padded > available:
        raise RuntimeError(
            f"not enough slack in Mach-O header to insert LC_LOAD_DYLIB "
            f"(need {padded}, have {available})"
        )

    data[header_end:header_end + padded] = new_cmd

    new_ncmds = ncmds + 1
    new_sizeofcmds = sizeofcmds + padded
    struct.pack_into('<II', data, 16, new_ncmds, new_sizeofcmds)


# ─── IPA packing ──────────────────────────────────────────────────────────
def unzip_ipa(ipa_path: Path, work_dir: Path) -> Path:
    with zipfile.ZipFile(ipa_path, 'r') as z:
        z.extractall(work_dir)
    payload = work_dir / 'Payload'
    apps = list(payload.glob('*.app'))
    if not apps:
        raise RuntimeError(f"no .app bundle found in {ipa_path}")
    if len(apps) > 1:
        raise RuntimeError(f"multiple .app bundles: {apps}")
    return apps[0]


def read_executable_name(app_dir: Path) -> str:
    plist_path = app_dir / 'Info.plist'
    if not plist_path.exists():
        raise RuntimeError(f"no Info.plist in {app_dir}")
    with open(plist_path, 'rb') as f:
        plist = plistlib.load(f)
    exe = plist.get('CFBundleExecutable')
    if not exe:
        raise RuntimeError("CFBundleExecutable not set")
    return exe


def repack_ipa(work_dir: Path, out_path: Path) -> None:
    # ZIP_DEFLATED matches what SideStore/LC expect; STORED would also work
    # but inflates the IPA size a lot.
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _dirs, files in os.walk(work_dir):
            for name in files:
                full = Path(root) / name
                rel  = full.relative_to(work_dir)
                z.write(full, rel.as_posix())


# ─── Main ─────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ipa', help='input IPA path')
    ap.add_argument('dylib', help='SpinLogger.dylib path')
    ap.add_argument('--out', help='output IPA path (default: <ipa>_SpinLogger.ipa)')
    ap.add_argument('--v4-model', help='optional path to v4_model.json bundle')
    ap.add_argument('--dylib-name', default='SpinLogger.dylib',
                    help='name the dylib ends up as inside the .app')
    args = ap.parse_args()

    ipa_path   = Path(args.ipa).resolve()
    dylib_path = Path(args.dylib).resolve()
    if not ipa_path.exists():
        sys.exit(f"IPA not found: {ipa_path}")
    if not dylib_path.exists():
        sys.exit(f"dylib not found: {dylib_path}")

    out_path = Path(args.out) if args.out else ipa_path.with_name(
        ipa_path.stem + '_SpinLogger.ipa'
    )

    print(f"[*] Input IPA:  {ipa_path}")
    print(f"[*] Dylib:      {dylib_path}")
    print(f"[*] Output IPA: {out_path}")

    with tempfile.TemporaryDirectory(prefix='spinlogger_inject_') as work:
        work_dir = Path(work)
        app_dir  = unzip_ipa(ipa_path, work_dir)
        exe_name = read_executable_name(app_dir)
        exe_path = app_dir / exe_name

        print(f"[*] .app:        {app_dir.name}")
        print(f"[*] Executable:  {exe_name}  ({exe_path.stat().st_size:,} bytes)")

        # Copy dylib.
        dest_dylib = app_dir / args.dylib_name
        shutil.copy2(dylib_path, dest_dylib)
        print(f"[+] Copied dylib → {args.dylib_name}")

        # Copy V4 model bundle if provided.
        if args.v4_model:
            src = Path(args.v4_model).resolve()
            if not src.exists():
                print(f"[!] v4_model not found: {src} — skipping")
            else:
                shutil.copy2(src, app_dir / 'v4_model.json')
                print(f"[+] Copied v4_model.json")

        # Remove One.dylib file if present (SpinLogger replaces it).
        one_file = app_dir / 'One.dylib'
        if one_file.exists():
            one_file.unlink()
            print(f"[+] Removed One.dylib file")

        # Patch Mach-O.
        with open(exe_path, 'rb') as f:
            data = bytearray(f.read())

        ncmds, sizeofcmds = read_header(bytes(data))
        print(f"[*] Mach-O: ncmds={ncmds} sizeofcmds={sizeofcmds}")

        # Drop existing One.dylib load commands (both possible paths).
        removed = 0
        for p in ('@executable_path/One.dylib', '@rpath/One.dylib'):
            r = remove_load_dylib(data, p)
            if r:
                print(f"[+] Removed {r} LC_LOAD_DYLIB for {p}")
                removed += r

        # Skip if our dylib is already injected.
        already = any(
            name == f'@executable_path/{args.dylib_name}'
            for _, _, name in iter_load_dylib(bytes(data))
        )
        if already:
            print(f"[*] LC_LOAD_DYLIB for {args.dylib_name} already present — skipping")
        else:
            inject_load_dylib(data, f'@executable_path/{args.dylib_name}')
            print(f"[+] Injected LC_LOAD_DYLIB @executable_path/{args.dylib_name}")

        with open(exe_path, 'wb') as f:
            f.write(bytes(data))

        ncmds2, sizeofcmds2 = read_header(bytes(data))
        print(f"[*] Mach-O now: ncmds={ncmds2} sizeofcmds={sizeofcmds2}")

        # Repack.
        print(f"[*] Repacking IPA ({out_path.name})...")
        repack_ipa(work_dir, out_path)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"[+] Done: {out_path}  ({size_mb:.1f} MB)")
    print()
    print("Next steps:")
    print("  1. Transfer to phone")
    print("  2. Import into LiveContainer")
    print("  3. Launch and check Documents/hook_breadcrumb.txt + hook_events.csv")


if __name__ == '__main__':
    main()
