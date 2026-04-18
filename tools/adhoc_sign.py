#!/usr/bin/env python3
"""
Ad-hoc code signer for Mach-O binaries.

Replaces the existing code signature with a fresh ad-hoc signature
that has correct SHA-256 page hashes for the current binary content.

This is needed after offline_patcher.py modifies __TEXT, because the
original code signature's page hashes no longer match.
"""

import struct
import sys
import hashlib
import os
import math

# Code signing constants
CSMAGIC_EMBEDDED_SIGNATURE = 0xFADE0CC0
CSMAGIC_CODEDIRECTORY      = 0xFADE0C02
CSMAGIC_REQUIREMENT        = 0xFADE0C00
CSMAGIC_REQUIREMENTS       = 0xFADE0C01

CSSLOT_CODEDIRECTORY = 0
CSSLOT_REQUIREMENTS  = 2

CS_ADHOC         = 0x0002
CS_LINKER_SIGNED = 0x20000
CS_HASHTYPE_SHA256 = 2
CS_SHA256_LEN      = 32
CS_PAGE_SHIFT      = 12
CS_PAGE_SIZE       = 1 << CS_PAGE_SHIFT  # 4096

# Code directory version
CD_VERSION_20400 = 0x20400


def build_code_directory(binary_data, code_limit, identifier, exec_seg_base, exec_seg_limit):
    """Build a CodeDirectory blob with SHA-256 page hashes."""

    # Number of code slots (pages)
    n_code_slots = int(math.ceil(code_limit / CS_PAGE_SIZE))

    # Special slots: we'll include an empty requirements slot
    n_special_slots = 2  # info.plist (slot -1) and requirements (slot -2)

    # Identifier bytes (null-terminated)
    ident_bytes = identifier.encode('ascii') + b'\x00'

    # CodeDirectory header size for version 0x20400
    # Base header: 44 bytes
    # + scatterOffset (4), teamOffset (4): version >= 0x20100, 0x20200
    # + spare3 (4), codeLimit64 (8): version >= 0x20300
    # + execSegBase (8), execSegLimit (8), execSegFlags (8): version >= 0x20400
    cd_header_size = 44 + 4 + 4 + 4 + 8 + 8 + 8 + 8  # = 88 bytes

    # Layout:
    # [header: cd_header_size bytes]
    # [identifier: len(ident_bytes) bytes]
    # [special slot hashes: n_special_slots * 32 bytes]
    # [code slot hashes: n_code_slots * 32 bytes]

    ident_offset = cd_header_size
    hash_offset = ident_offset + len(ident_bytes) + n_special_slots * CS_SHA256_LEN
    total_size = hash_offset + n_code_slots * CS_SHA256_LEN

    cd = bytearray(total_size)

    # Header (big-endian for magic/length, mixed for rest per Apple spec)
    # Actually, the entire CodeDirectory is big-endian
    struct.pack_into('>I', cd, 0, CSMAGIC_CODEDIRECTORY)  # magic
    struct.pack_into('>I', cd, 4, total_size)              # length
    struct.pack_into('>I', cd, 8, CD_VERSION_20400)        # version
    struct.pack_into('>I', cd, 12, CS_ADHOC | CS_LINKER_SIGNED)  # flags
    struct.pack_into('>I', cd, 16, hash_offset)            # hashOffset
    struct.pack_into('>I', cd, 20, ident_offset)           # identOffset
    struct.pack_into('>I', cd, 24, n_special_slots)        # nSpecialSlots
    struct.pack_into('>I', cd, 28, n_code_slots)           # nCodeSlots
    struct.pack_into('>I', cd, 32, min(code_limit, 0xFFFFFFFF))  # codeLimit (32-bit)
    cd[36] = CS_SHA256_LEN                                  # hashSize
    cd[37] = CS_HASHTYPE_SHA256                             # hashType
    cd[38] = 0                                              # platform
    cd[39] = CS_PAGE_SHIFT                                  # pageSize (log2)
    struct.pack_into('>I', cd, 40, 0)                       # spare2

    # Version 0x20100 fields
    struct.pack_into('>I', cd, 44, 0)                       # scatterOffset
    # Version 0x20200 fields
    struct.pack_into('>I', cd, 48, 0)                       # teamOffset
    # Version 0x20300 fields
    struct.pack_into('>I', cd, 52, 0)                       # spare3
    struct.pack_into('>Q', cd, 56, code_limit)              # codeLimit64
    # Version 0x20400 fields
    struct.pack_into('>Q', cd, 64, exec_seg_base)           # execSegBase
    struct.pack_into('>Q', cd, 72, exec_seg_limit)          # execSegLimit
    struct.pack_into('>Q', cd, 80, 0)                       # execSegFlags

    # Write identifier
    cd[ident_offset:ident_offset + len(ident_bytes)] = ident_bytes

    # Compute special slot hashes (slots are numbered -n_special_slots to -1)
    # Slot -2 (CSSLOT_REQUIREMENTS): empty requirements blob hash
    # Slot -1 (info.plist): all zeros (not present)
    # Special slots are stored before code slots, in reverse order
    # Index 0 = slot -n_special_slots, index n-1 = slot -1

    # Build empty requirements blob for hashing
    empty_req = struct.pack('>II', CSMAGIC_REQUIREMENTS, 12) + struct.pack('>I', 0)
    req_hash = hashlib.sha256(empty_req).digest()

    special_start = ident_offset + len(ident_bytes)
    # Slot -2 (requirements) at index 0
    cd[special_start:special_start + 32] = req_hash
    # Slot -1 (info.plist) at index 1 — all zeros (absent)

    # Compute code slot hashes
    print("  Computing %d page hashes..." % n_code_slots)
    for i in range(n_code_slots):
        page_start = i * CS_PAGE_SIZE
        page_end = min(page_start + CS_PAGE_SIZE, code_limit)
        page_data = binary_data[page_start:page_end]
        h = hashlib.sha256(page_data).digest()
        off = hash_offset + i * CS_SHA256_LEN
        cd[off:off + 32] = h

    return bytes(cd), empty_req


def build_superblob(cd_blob, req_blob):
    """Build a SuperBlob (embedded signature) containing CodeDirectory and Requirements."""
    # SuperBlob header: magic(4) + length(4) + count(4) = 12 bytes
    # BlobIndex entries: 2 * (type(4) + offset(4)) = 16 bytes
    # Total header: 28 bytes

    n_blobs = 2
    header_size = 12 + n_blobs * 8

    cd_offset = header_size
    req_offset = cd_offset + len(cd_blob)
    total_size = req_offset + len(req_blob)

    sb = bytearray(total_size)

    struct.pack_into('>I', sb, 0, CSMAGIC_EMBEDDED_SIGNATURE)  # magic
    struct.pack_into('>I', sb, 4, total_size)                   # length
    struct.pack_into('>I', sb, 8, n_blobs)                      # count

    # BlobIndex[0]: CodeDirectory
    struct.pack_into('>I', sb, 12, CSSLOT_CODEDIRECTORY)
    struct.pack_into('>I', sb, 16, cd_offset)

    # BlobIndex[1]: Requirements
    struct.pack_into('>I', sb, 20, CSSLOT_REQUIREMENTS)
    struct.pack_into('>I', sb, 24, req_offset)

    # Blobs
    sb[cd_offset:cd_offset + len(cd_blob)] = cd_blob
    sb[req_offset:req_offset + len(req_blob)] = req_blob

    return bytes(sb)


def resign_binary(input_path, output_path):
    print("[*] Reading binary: %s" % input_path)
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())

    # Parse Mach-O header
    magic = struct.unpack_from('<I', data, 0)[0]
    if magic != 0xFEEDFACF:
        print("[!] Not a 64-bit Mach-O (magic=0x%08x)" % magic)
        return False

    ncmds = struct.unpack_from('<I', data, 16)[0]
    sizeofcmds = struct.unpack_from('<I', data, 20)[0]

    # Find LC_CODE_SIGNATURE and __TEXT segment
    pos = 32
    codesig_pos = -1
    codesig_dataoff = 0
    codesig_datasize = 0
    text_fileoff = 0
    text_filesize = 0
    linkedit_pos = -1
    linkedit_fileoff = 0
    linkedit_filesize = 0
    linkedit_vmaddr = 0

    for i in range(ncmds):
        cmd, cmdsize = struct.unpack_from('<II', data, pos)
        if cmd == 0x1D:  # LC_CODE_SIGNATURE
            codesig_pos = pos
            codesig_dataoff, codesig_datasize = struct.unpack_from('<II', data, pos + 8)
            print("[*] Found LC_CODE_SIGNATURE: dataoff=0x%x datasize=0x%x" % (codesig_dataoff, codesig_datasize))
        elif cmd == 0x19:  # LC_SEGMENT_64
            segname = data[pos+8:pos+24].split(b'\x00')[0].decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', data, pos+24)
            if segname == '__TEXT':
                text_fileoff = fileoff
                text_filesize = filesize
            elif segname == '__LINKEDIT':
                linkedit_pos = pos
                linkedit_fileoff = fileoff
                linkedit_filesize = filesize
                linkedit_vmaddr = vmaddr
        pos += cmdsize

    if codesig_pos < 0:
        print("[!] No LC_CODE_SIGNATURE found")
        return False

    # The code limit is the start of the code signature data
    code_limit = codesig_dataoff
    print("[*] Code limit: 0x%x (%d bytes, %d pages)" % (
        code_limit, code_limit, int(math.ceil(code_limit / CS_PAGE_SIZE))))

    # Build identifier from the binary name
    identifier = os.path.splitext(os.path.basename(input_path))[0]
    # Clean up identifier (remove .patched2 etc)
    for suffix in ['.patched2', '.patched', '.signed']:
        if identifier.endswith(suffix.replace('.', '')):
            identifier = identifier[:-(len(suffix)-1)]
    if identifier.startswith('UnityFramework'):
        identifier = 'UnityFramework'
    print("[*] Identifier: %s" % identifier)

    # Zero out the binary content from code_limit to end of old signature
    # (this is the region we'll replace with our new signature)
    old_sig_end = codesig_dataoff + codesig_datasize

    # Build new signature using the binary content up to code_limit
    # (we hash the binary content BEFORE the signature)
    binary_to_hash = bytes(data[:code_limit])

    print("[*] Building ad-hoc code signature...")
    cd_blob, req_blob = build_code_directory(
        binary_to_hash, code_limit, identifier,
        exec_seg_base=text_fileoff, exec_seg_limit=text_filesize)

    superblob = build_superblob(cd_blob, req_blob)
    print("[*] New signature size: %d bytes (was %d)" % (len(superblob), codesig_datasize))

    # Check if new signature fits in the old slot
    if len(superblob) > codesig_datasize:
        print("[!] New signature (%d) larger than old (%d) — need to resize" % (
            len(superblob), codesig_datasize))
        # We need to extend the file or adjust __LINKEDIT
        # For now, just pad to fit
        # Actually this is very unlikely — our signature should be smaller
        return False

    # Write new signature into the binary
    # First, zero out the old signature area
    for i in range(codesig_dataoff, min(old_sig_end, len(data))):
        data[i] = 0

    # Write new signature
    data[codesig_dataoff:codesig_dataoff + len(superblob)] = superblob

    # Update LC_CODE_SIGNATURE to point to new signature
    # dataoff stays the same, datasize updates
    struct.pack_into('<I', data, codesig_pos + 8, codesig_dataoff)
    struct.pack_into('<I', data, codesig_pos + 12, len(superblob))

    # Update __LINKEDIT segment size to match
    # __LINKEDIT.filesize should cover from linkedit_fileoff to the end of our new signature
    new_linkedit_filesize = (codesig_dataoff + len(superblob)) - linkedit_fileoff
    # Align up to page boundary
    new_linkedit_filesize = (new_linkedit_filesize + CS_PAGE_SIZE - 1) & ~(CS_PAGE_SIZE - 1)

    # Keep original LINKEDIT size (it's large enough)
    # Just make sure we don't write beyond the file

    # Truncate file to remove excess (optional, keeps file clean)
    new_file_size = codesig_dataoff + len(superblob)
    # Align to 16 bytes
    new_file_size = (new_file_size + 15) & ~15

    # Update __LINKEDIT filesize and vmsize
    new_linkedit_filesize = new_file_size - linkedit_fileoff
    new_linkedit_vmsize = (new_linkedit_filesize + CS_PAGE_SIZE - 1) & ~(CS_PAGE_SIZE - 1)

    if linkedit_pos >= 0:
        # Update filesize
        struct.pack_into('<Q', data, linkedit_pos + 48, new_linkedit_filesize)
        # Update vmsize
        struct.pack_into('<Q', data, linkedit_pos + 32, new_linkedit_vmsize)
        print("[*] Updated __LINKEDIT: filesize=0x%x vmsize=0x%x" % (
            new_linkedit_filesize, new_linkedit_vmsize))

    # Truncate
    data = data[:new_file_size]

    # Write output
    print("[*] Writing re-signed binary: %s (%d bytes)" % (output_path, len(data)))
    with open(output_path, 'wb') as f:
        f.write(data)

    print("[+] Ad-hoc signing complete!")
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 adhoc_sign.py <macho_binary> [output]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path + '.signed'

    success = resign_binary(input_path, output_path)
    sys.exit(0 if success else 1)
