#!/usr/bin/env python3
"""
Combined patcher + signature fixer.

Instead of replacing the entire code signature (which breaks LiveContainer),
this script:
  1. Patches the binary (trampolines, hookslots) — same as offline_patcher.py
  2. Parses the EXISTING code signature
  3. Recomputes ONLY the page hashes for pages we actually modified
  4. Writes the updated hashes back into the existing CodeDirectory

This preserves the original signature structure (flags, identifier, entitlements,
team ID, requirements, CMS blob, etc.) — only the page hashes change.
"""

import struct
import sys
import os
import hashlib
import math

# Import the patcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from offline_patcher import (
    parse_discovery, parse_macho_segments, find_code_cave, find_data_cave,
    va_to_fileoff, fileoff_to_va, encode_b, encode_adrp, encode_ldr_x_uoff,
    encode_br, encode_cbnz_x, insn_bytes,
    HOOKSLOT_MAGIC0, HOOKSLOT_MAGIC1
)

# Code signing constants
CSMAGIC_EMBEDDED_SIGNATURE = 0xFADE0CC0
CSMAGIC_CODEDIRECTORY      = 0xFADE0C02
CSMAGIC_CMS_SIGNATURE      = 0xFADE0B01
CSSLOT_CMS_SIGNATURE       = 0x10000
CS_ADHOC                   = 0x0002
CS_HASHTYPE_SHA1   = 1
CS_HASHTYPE_SHA256 = 2


def find_code_signature(data):
    """Find LC_CODE_SIGNATURE load command and return (dataoff, datasize, lc_pos)."""
    magic = struct.unpack_from('<I', data, 0)[0]
    assert magic == 0xFEEDFACF, "Not a 64-bit Mach-O"

    ncmds = struct.unpack_from('<I', data, 16)[0]
    sizeofcmds = struct.unpack_from('<I', data, 20)[0]

    pos = 32
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from('<II', data, pos)
        if cmd == 0x1D:  # LC_CODE_SIGNATURE
            dataoff, datasize = struct.unpack_from('<II', data, pos + 8)
            return dataoff, datasize, pos
        pos += cmdsize
    return None, None, None


def parse_superblob(data, sig_off):
    """Parse the SuperBlob and find CodeDirectory blobs."""
    magic = struct.unpack_from('>I', data, sig_off)[0]
    if magic != CSMAGIC_EMBEDDED_SIGNATURE:
        print("[!] Not a SuperBlob at 0x%x (magic=0x%08x)" % (sig_off, magic))
        return []

    length = struct.unpack_from('>I', data, sig_off + 4)[0]
    count = struct.unpack_from('>I', data, sig_off + 8)[0]

    cds = []
    for i in range(count):
        blob_type = struct.unpack_from('>I', data, sig_off + 12 + i * 8)[0]
        blob_off = struct.unpack_from('>I', data, sig_off + 12 + i * 8 + 4)[0]
        abs_off = sig_off + blob_off
        blob_magic = struct.unpack_from('>I', data, abs_off)[0]

        if blob_magic == CSMAGIC_CODEDIRECTORY:
            cds.append((blob_type, abs_off))

    return cds


def parse_codedirectory(data, cd_off):
    """Parse a CodeDirectory and return its parameters."""
    magic = struct.unpack_from('>I', data, cd_off)[0]
    assert magic == CSMAGIC_CODEDIRECTORY

    cd_length = struct.unpack_from('>I', data, cd_off + 4)[0]
    version = struct.unpack_from('>I', data, cd_off + 8)[0]
    flags = struct.unpack_from('>I', data, cd_off + 12)[0]
    hash_offset = struct.unpack_from('>I', data, cd_off + 16)[0]
    ident_offset = struct.unpack_from('>I', data, cd_off + 20)[0]
    n_special_slots = struct.unpack_from('>I', data, cd_off + 24)[0]
    n_code_slots = struct.unpack_from('>I', data, cd_off + 28)[0]
    code_limit = struct.unpack_from('>I', data, cd_off + 32)[0]
    hash_size = data[cd_off + 36]
    hash_type = data[cd_off + 37]
    page_size_log2 = data[cd_off + 39]
    page_size = 1 << page_size_log2

    # Check for 64-bit code limit (version >= 0x20300)
    code_limit_64 = code_limit
    if version >= 0x20300:
        spare3 = struct.unpack_from('>I', data, cd_off + 52)[0]
        cl64 = struct.unpack_from('>Q', data, cd_off + 56)[0]
        if cl64 > 0:
            code_limit_64 = cl64

    return {
        'offset': cd_off,
        'length': cd_length,
        'version': version,
        'flags': flags,
        'hash_offset': hash_offset,
        'n_special_slots': n_special_slots,
        'n_code_slots': n_code_slots,
        'code_limit': code_limit_64,
        'hash_size': hash_size,
        'hash_type': hash_type,
        'page_size': page_size,
    }


def hash_page(page_data, hash_type):
    """Compute a page hash using the specified hash type."""
    if hash_type == CS_HASHTYPE_SHA1:
        return hashlib.sha1(page_data).digest()
    elif hash_type == CS_HASHTYPE_SHA256:
        return hashlib.sha256(page_data).digest()
    else:
        raise ValueError("Unknown hash type: %d" % hash_type)


def fix_page_hashes(data, cd_info, modified_pages):
    """Recompute and write hashes for modified pages in a CodeDirectory."""
    cd_off = cd_info['offset']
    hash_offset = cd_info['hash_offset']
    hash_size = cd_info['hash_size']
    hash_type = cd_info['hash_type']
    page_size = cd_info['page_size']
    code_limit = cd_info['code_limit']
    n_code_slots = cd_info['n_code_slots']

    fixed = 0
    for page_idx in modified_pages:
        if page_idx >= n_code_slots:
            print("    WARNING: page %d beyond n_code_slots %d, skipping" % (
                page_idx, n_code_slots))
            continue

        # Compute new hash for this page
        page_start = page_idx * page_size
        page_end = min(page_start + page_size, code_limit)
        page_data = bytes(data[page_start:page_end])
        new_hash = hash_page(page_data, hash_type)

        # Read old hash
        hash_file_off = cd_off + hash_offset + page_idx * hash_size
        old_hash = bytes(data[hash_file_off:hash_file_off + hash_size])

        if old_hash != new_hash:
            data[hash_file_off:hash_file_off + hash_size] = new_hash
            fixed += 1

    return fixed


def set_adhoc_flag(data, cd_info):
    """Set the CS_ADHOC flag in a CodeDirectory so the kernel
    validates page hashes directly instead of requiring a CMS signature."""
    cd_off = cd_info['offset']
    flags = struct.unpack_from('>I', data, cd_off + 12)[0]
    if not (flags & CS_ADHOC):
        flags |= CS_ADHOC
        struct.pack_into('>I', data, cd_off + 12, flags)
        return True
    return False


def strip_cms_signature(data, sig_off, sig_size):
    """Rebuild the SuperBlob in-place, removing the CMS_SIGNATURE blob.
    Returns (new_superblob_size, blobs_removed)."""
    magic = struct.unpack_from('>I', data, sig_off)[0]
    if magic != CSMAGIC_EMBEDDED_SIGNATURE:
        print("[!] Not a SuperBlob")
        return sig_size, 0

    old_length = struct.unpack_from('>I', data, sig_off + 4)[0]
    count = struct.unpack_from('>I', data, sig_off + 8)[0]

    # Read all blob index entries
    blobs = []
    for i in range(count):
        blob_type = struct.unpack_from('>I', data, sig_off + 12 + i * 8)[0]
        blob_off = struct.unpack_from('>I', data, sig_off + 12 + i * 8 + 4)[0]
        abs_off = sig_off + blob_off
        blob_len = struct.unpack_from('>I', data, abs_off + 4)[0]
        blobs.append((blob_type, blob_off, abs_off, blob_len))

    # Separate CMS from non-CMS blobs
    keep = [(t, o, a, l) for t, o, a, l in blobs if t != CSSLOT_CMS_SIGNATURE]
    removed = len(blobs) - len(keep)
    if removed == 0:
        print("[*] No CMS_SIGNATURE blob found — nothing to strip")
        return sig_size, 0

    print("[*] Stripping %d CMS_SIGNATURE blob(s) from SuperBlob" % removed)

    # Build new SuperBlob: header + index entries + blob data
    new_count = len(keep)
    new_header_size = 12 + new_count * 8  # magic(4) + length(4) + count(4) + index(n*8)

    # Collect blob data in order
    blob_data_list = []
    for t, o, a, l in keep:
        blob_data_list.append((t, bytes(data[a:a + l])))

    # Calculate new offsets
    cursor = new_header_size
    new_entries = []
    for t, bd in blob_data_list:
        new_entries.append((t, cursor, bd))
        cursor += len(bd)

    new_total = cursor

    # Zero out old signature area
    for i in range(sig_off, sig_off + old_length):
        if i < len(data):
            data[i] = 0

    # Write new SuperBlob header
    struct.pack_into('>I', data, sig_off, CSMAGIC_EMBEDDED_SIGNATURE)
    struct.pack_into('>I', data, sig_off + 4, new_total)
    struct.pack_into('>I', data, sig_off + 8, new_count)

    # Write blob index entries
    for i, (t, off, bd) in enumerate(new_entries):
        struct.pack_into('>I', data, sig_off + 12 + i * 8, t)
        struct.pack_into('>I', data, sig_off + 12 + i * 8 + 4, off)

    # Write blob data
    for t, off, bd in new_entries:
        data[sig_off + off:sig_off + off + len(bd)] = bd

    print("[*] SuperBlob: %d -> %d bytes (removed %d bytes)" % (
        old_length, new_total, old_length - new_total))

    return new_total, removed


def inject_load_dylib(data, dylib_path="@rpath/SpinLogger.dylib"):
    """Inject an LC_LOAD_DYLIB command for the given dylib into the Mach-O header.
    Returns True if injected, False if already present or no room."""
    LC_LOAD_DYLIB = 0x0C

    ncmds = struct.unpack_from('<I', data, 16)[0]
    sizeofcmds = struct.unpack_from('<I', data, 20)[0]
    header_size = 32
    end_of_cmds = header_size + sizeofcmds

    # Check if already present
    pos = 32
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from('<II', data, pos)
        if cmd == LC_LOAD_DYLIB:
            name_off = struct.unpack_from('<I', data, pos + 8)[0]
            name = data[pos + name_off:pos + cmdsize].split(b'\x00')[0].decode()
            if dylib_path in name:
                print("[*] LC_LOAD_DYLIB for %s already present" % dylib_path)
                return False
        pos += cmdsize

    # Build the load command
    name_bytes = dylib_path.encode('ascii') + b'\x00'
    name_offset = 24  # size of dylib_command header
    raw_size = name_offset + len(name_bytes)
    # Align to 8 bytes
    cmdsize = (raw_size + 7) & ~7

    lc = bytearray(cmdsize)
    struct.pack_into('<I', lc, 0, LC_LOAD_DYLIB)    # cmd
    struct.pack_into('<I', lc, 4, cmdsize)            # cmdsize
    struct.pack_into('<I', lc, 8, name_offset)        # name offset
    struct.pack_into('<I', lc, 12, 0)                 # timestamp
    struct.pack_into('<I', lc, 16, 0x00010000)        # current_version (1.0.0)
    struct.pack_into('<I', lc, 20, 0x00010000)        # compat_version (1.0.0)
    lc[name_offset:name_offset + len(name_bytes)] = name_bytes

    # Check room
    # Find first section data offset to know the boundary
    pos = 32
    first_section_off = len(data)
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from('<II', data, pos)
        if cmd == 0x19:  # LC_SEGMENT_64
            nsects = struct.unpack_from('<I', data, pos + 64)[0]
            sec_pos = pos + 72
            for _ in range(nsects):
                soff = struct.unpack_from('<I', data, sec_pos + 48)[0]
                if soff > 0 and soff < first_section_off:
                    first_section_off = soff
                sec_pos += 80
        pos += cs

    available = first_section_off - end_of_cmds
    if cmdsize > available:
        print("[!] No room for LC_LOAD_DYLIB (%d bytes needed, %d available)" % (
            cmdsize, available))
        return False

    # Write the load command at end_of_cmds
    data[end_of_cmds:end_of_cmds + cmdsize] = lc

    # Update header: ncmds and sizeofcmds
    struct.pack_into('<I', data, 16, ncmds + 1)
    struct.pack_into('<I', data, 20, sizeofcmds + cmdsize)

    print("[+] Injected LC_LOAD_DYLIB for %s (%d bytes at 0x%x)" % (
        dylib_path, cmdsize, end_of_cmds))
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 patch_and_fixsig.py <binary> <discovery.txt> [output]")
        sys.exit(1)

    binary_path = sys.argv[1]
    discovery_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else binary_path + '.patched'

    print("[*] Loading binary: %s" % binary_path)
    with open(binary_path, 'rb') as f:
        data = bytearray(f.read())
    original_size = len(data)

    # ── Step 0: Optionally inject LC_LOAD_DYLIB ──
    dylib_injected = False
    if '--inject-dylib' in sys.argv:
        print("[*] Injecting LC_LOAD_DYLIB for SpinLogger.dylib...")
        dylib_injected = inject_load_dylib(data)
    else:
        print("[*] Skipping LC_LOAD_DYLIB (LiveContainer handles injection)")

    # ── Step 1: Parse discovery ──
    print("[*] Parsing discovery: %s" % discovery_path)
    methods, disc_segs, image_path = parse_discovery(discovery_path)
    if not methods:
        print("[!] No methods found")
        sys.exit(1)
    print("[*] Found %d methods" % len(methods))

    # ── Step 2: Parse Mach-O ──
    segments, fat_base, sections = parse_macho_segments(data)
    text_seg = next((s for s in segments if s.name == '__TEXT'), None)
    data_seg = next((s for s in segments if s.name == '__DATA'), None)

    # ── Step 3: Find code signature BEFORE patching ──
    sig_off, sig_size, lc_pos = find_code_signature(data)
    if sig_off is None:
        print("[!] No LC_CODE_SIGNATURE found")
        sys.exit(1)
    print("[*] Code signature at fileoff 0x%x, size 0x%x" % (sig_off, sig_size))

    # Parse all CodeDirectories (there may be multiple: SHA-1 + SHA-256)
    cd_list = parse_superblob(data, sig_off)
    print("[*] Found %d CodeDirectory blob(s)" % len(cd_list))
    cd_infos = []
    for slot_type, cd_off in cd_list:
        info = parse_codedirectory(data, cd_off)
        ht_name = {1: 'SHA-1', 2: 'SHA-256'}.get(info['hash_type'], 'unknown')
        print("    CD slot=0x%x: %s, %d pages, hash_size=%d, page_size=%d, code_limit=0x%x" % (
            slot_type, ht_name, info['n_code_slots'],
            info['hash_size'], info['page_size'], info['code_limit']))
        cd_infos.append(info)

    if not cd_infos:
        print("[!] No CodeDirectory found in signature")
        sys.exit(1)

    # ── Step 4: Verify prologues ──
    for m in methods:
        foff = va_to_fileoff(m.unslid_va, segments, fat_base)
        actual = data[foff:foff + 32]
        if actual != m.prologue_bytes:
            print("[!] %s prologue mismatch!" % m.name)
            sys.exit(1)
        print("[+] %s: prologue OK at 0x%x" % (m.name, foff))

    # ── Step 5: Find caves ──
    num_methods = len(methods)
    cave_need = num_methods * 32
    data_need = 16 + num_methods * 16

    cave_off, cave_avail = find_code_cave(data, text_seg, cave_need)
    if cave_off < 0:
        print("[!] No code cave found")
        sys.exit(1)
    print("[+] Code cave at 0x%x (%d bytes)" % (cave_off, cave_avail))

    dcave_off, dcave_avail = find_data_cave(data, data_seg, data_need, sections)
    if dcave_off < 0:
        print("[!] No data cave found")
        sys.exit(1)
    print("[+] Data cave at 0x%x (%d bytes)" % (dcave_off, dcave_avail))

    # ── Step 6: Track which pages we modify ──
    page_size = cd_infos[0]['page_size']  # Use first CD's page size
    modified_pages = set()

    # Include pages modified by dylib injection (header at offset 16-23, load cmd)
    if dylib_injected:
        ncmds_now = struct.unpack_from('<I', data, 16)[0]
        sizeofcmds_now = struct.unpack_from('<I', data, 20)[0]
        lc_end = 32 + sizeofcmds_now
        modified_pages.add(0)  # page 0: Mach-O header (ncmds, sizeofcmds)
        modified_pages.add((lc_end - 48) // page_size)  # page with new load command

    def mark_modified(fileoff, size=4):
        start_page = fileoff // page_size
        end_page = (fileoff + size - 1) // page_size
        for p in range(start_page, end_page + 1):
            modified_pages.add(p)

    # ── Step 7: Apply patches (same logic as offline_patcher.py) ──

    # Write hookslot table magic
    hookslot_table_off = dcave_off
    struct.pack_into('<Q', data, hookslot_table_off, HOOKSLOT_MAGIC0)
    struct.pack_into('<Q', data, hookslot_table_off + 8, HOOKSLOT_MAGIC1)
    mark_modified(hookslot_table_off, 16)

    hookslots_off = hookslot_table_off + 16
    origvas_off = hookslots_off + num_methods * 8

    for i in range(4):
        struct.pack_into('<Q', data, hookslots_off + i * 8, 0)
        struct.pack_into('<Q', data, origvas_off + i * 8, 0)
    mark_modified(hookslots_off, num_methods * 8)
    mark_modified(origvas_off, num_methods * 8)

    tramp_cursor = cave_off
    for i, m in enumerate(methods):
        target_foff = va_to_fileoff(m.unslid_va, segments, fat_base)
        target_va = m.unslid_va
        orig_insn = struct.unpack_from('<I', data, target_foff)[0]

        tramp_va = fileoff_to_va(tramp_cursor, segments, fat_base)
        hookslot_va = fileoff_to_va(hookslots_off + i * 8, segments, fat_base)

        insn0 = encode_adrp(16, tramp_va, hookslot_va)
        insn1 = encode_ldr_x_uoff(16, 16, hookslot_va & 0xFFF)
        insn2 = encode_cbnz_x(16, 8)

        orig_stub_off = tramp_cursor + 20
        orig_stub_va = fileoff_to_va(orig_stub_off, segments, fat_base)
        insn3 = encode_b(orig_stub_va - (tramp_va + 12))
        insn4 = encode_br(16)

        # Write trampoline
        struct.pack_into('<I', data, tramp_cursor + 0, insn0)
        struct.pack_into('<I', data, tramp_cursor + 4, insn1)
        struct.pack_into('<I', data, tramp_cursor + 8, insn2)
        struct.pack_into('<I', data, tramp_cursor + 12, insn3)
        struct.pack_into('<I', data, tramp_cursor + 16, insn4)
        mark_modified(tramp_cursor, 20)

        # Write orig stub
        b_back_offset = (target_va + 4) - (orig_stub_va + 4)
        struct.pack_into('<I', data, orig_stub_off + 0, orig_insn)
        struct.pack_into('<I', data, orig_stub_off + 4, encode_b(b_back_offset))
        mark_modified(orig_stub_off, 8)

        # Write origVA
        struct.pack_into('<Q', data, origvas_off + i * 8, orig_stub_va)

        # Patch target prologue
        patch_insn = encode_b(tramp_va - target_va)
        struct.pack_into('<I', data, target_foff, patch_insn)
        mark_modified(target_foff, 4)

        tramp_cursor = (orig_stub_off + 8 + 3) & ~3

        print("[+] Patched %s: target=0x%x tramp=0x%x hookslot=0x%x" % (
            m.name, target_va, tramp_va, hookslot_va))

    # ── Step 8: Fix code signature page hashes ──
    print("\n[*] Modified %d pages, fixing code signature..." % len(modified_pages))
    sorted_pages = sorted(modified_pages)
    print("    Pages: %s" % ', '.join('0x%x' % (p * page_size) for p in sorted_pages))

    for cd_info in cd_infos:
        ht_name = {1: 'SHA-1', 2: 'SHA-256'}.get(cd_info['hash_type'], '?')
        fixed = fix_page_hashes(data, cd_info, modified_pages)
        print("[+] Fixed %d/%d hashes in %s CodeDirectory" % (
            fixed, len(modified_pages), ht_name))

    # ── Step 8b: Strip CMS_SIGNATURE from SuperBlob ──
    # CMS blob cryptographically signs the CodeDirectory — since we modified
    # page hashes, the CMS signature is invalid. Stripping it forces the
    # kernel to fall back to validating individual page hashes from the CD.
    # We keep the original LC_CODE_SIGNATURE datasize and don't set CS_ADHOC
    # to avoid disrupting LiveContainer's signing flow.
    print("\n[*] Stripping CMS_SIGNATURE from SuperBlob...")
    new_sig_size, n_removed = strip_cms_signature(data, sig_off, sig_size)

    if n_removed > 0:
        print("[*] Keeping original LC_CODE_SIGNATURE datasize=0x%x (SuperBlob=%d, rest is padding)" % (
            sig_size, new_sig_size))

    # ── Step 9: Write output (same size as original!) ──
    assert len(data) == original_size, "File size changed! Was %d, now %d" % (
        original_size, len(data))

    print("[*] Writing: %s (%d bytes, same as original)" % (output_path, len(data)))
    with open(output_path, 'wb') as f:
        f.write(data)

    print("[+] Done! Binary patched with %d methods, signature hashes fixed, CMS stripped." % len(methods))


if __name__ == '__main__':
    main()
