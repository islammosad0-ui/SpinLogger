#!/usr/bin/env python3
"""
SpinLogger Offline Binary Patcher

Patches the CoinMaster Mach-O binary to redirect target functions through
hookslots in __DATA. This avoids runtime __TEXT modification, which is
blocked by iOS code-signing enforcement (CS_KILL).

Workflow:
  1. Run app with DIAG mode → produces hook_discovery.txt
  2. Run this patcher: python3 offline_patcher.py <binary> <discovery.txt>
  3. Replace the binary in the IPA
  4. Sideload (re-signs the binary, new hashes include our patches)
  5. Set hook_config.txt to "HOOKSLOT"
  6. Hooks work — SpinLogger.dylib writes hook addrs to __DATA hookslots

Architecture:
  For each target function:
    - Prologue instruction 1 → B <trampoline>  (4 bytes)
    - Trampoline (code cave):
        ADRP X16, hookslot@PAGE
        LDR  X16, [X16, hookslot@PAGEOFF]
        CBNZ X16, +8
        B    orig_stub
        BR   X16
    - Orig stub (code cave):
        <saved_original_insn>
        B    <target + 4>
    - Hookslot (__DATA):
        8 bytes, initially 0 → dylib writes hook function addr at runtime

  Hookslot table in __DATA:
    [8B MAGIC0] [8B MAGIC1]
    [hookslot_0] [hookslot_1] [hookslot_2] [hookslot_3]
    [origVA_0]   [origVA_1]   [origVA_2]   [origVA_3]
"""

import struct
import sys
import os
import shutil
import re

# Magic markers — must match SLSpinHook.m
HOOKSLOT_MAGIC0 = 0xDEADBEEF5350494E
HOOKSLOT_MAGIC1 = 0x484F4F4B534C4F54

# ─── ARM64 instruction encoders ────────────────────────────────────────

def encode_b(offset_bytes):
    """B <offset> — PC-relative branch, ±128MB."""
    assert offset_bytes % 4 == 0, f"B offset must be 4-byte aligned: {offset_bytes}"
    imm26 = (offset_bytes >> 2) & 0x03FFFFFF
    return 0x14000000 | imm26

def encode_adrp(rd, pc, target):
    """ADRP Xd, target@PAGE — ±4GB PC-relative page load."""
    pc_page = pc & ~0xFFF
    target_page = target & ~0xFFF
    imm = (target_page - pc_page) >> 12
    # Handle negative values (two's complement for 21-bit)
    imm &= 0x1FFFFF
    immlo = imm & 0x3
    immhi = (imm >> 2) & 0x7FFFF
    return 0x90000000 | (immhi << 5) | (immlo << 29) | rd

def encode_ldr_x_uoff(rt, rn, offset):
    """LDR Xt, [Xn, #offset] — unsigned offset, 8-byte aligned."""
    assert offset % 8 == 0, f"LDR offset must be 8-byte aligned: {offset}"
    assert 0 <= offset < 32768, f"LDR offset out of range: {offset}"
    imm12 = (offset >> 3) & 0xFFF
    return 0xF9400000 | (imm12 << 10) | (rn << 5) | rt

def encode_br(rn):
    """BR Xn — branch to register."""
    return 0xD61F0000 | (rn << 5)

def encode_cbnz_x(rt, offset_bytes):
    """CBNZ Xt, <offset> — compare and branch if nonzero."""
    assert offset_bytes % 4 == 0
    imm19 = (offset_bytes >> 2) & 0x7FFFF
    return 0xB5000000 | (imm19 << 5) | rt

def encode_nop():
    return 0xD503201F

def insn_bytes(insn):
    """Encode a 32-bit instruction to 4 little-endian bytes."""
    return struct.pack('<I', insn)

# ─── Mach-O parser (minimal, just what we need) ───────────────────────

class Segment:
    def __init__(self, name, vmaddr, vmsize, fileoff, filesize):
        self.name = name
        self.vmaddr = vmaddr
        self.vmsize = vmsize
        self.fileoff = fileoff
        self.filesize = filesize

def parse_macho_segments(data):
    """Parse LC_SEGMENT_64 commands from a 64-bit Mach-O binary."""
    magic = struct.unpack_from('<I', data, 0)[0]
    if magic == 0xBEBAFECA:
        # Fat binary — find arm64 slice
        nfat = struct.unpack_from('>I', data, 4)[0]
        for i in range(nfat):
            off = 8 + i * 20
            cpu, sub, sliceoff, slicesize, align = struct.unpack_from('>IIIII', data, off)
            if cpu == 0x0100000C:  # CPU_TYPE_ARM64
                print("  Fat binary: arm64 slice at offset 0x%x, size 0x%x" % (sliceoff, slicesize))
                return parse_macho_segments_at(data, sliceoff)
        raise ValueError("No arm64 slice found in fat binary")
    elif magic == 0xFEEDFACF:  # MH_MAGIC_64
        return parse_macho_segments_at(data, 0)
    else:
        raise ValueError("Not a Mach-O binary (magic=0x%08x)" % magic)

class Section:
    def __init__(self, name, segname, addr, size, offset):
        self.name = name
        self.segname = segname
        self.addr = addr
        self.size = size
        self.offset = offset  # file offset (0 for BSS sections)

def parse_macho_segments_at(data, base):
    """Parse segments and sections from a Mach-O at a given offset."""
    magic, cputype, cpusub, filetype, ncmds, sizeofcmds, flags, reserved = \
        struct.unpack_from('<IIIIIIII', data, base)
    assert magic == 0xFEEDFACF, "Expected MH_MAGIC_64, got 0x%08x" % magic

    segments = []
    all_sections = []
    pos = base + 32  # sizeof(mach_header_64)
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from('<II', data, pos)
        if cmd == 0x19:  # LC_SEGMENT_64
            segname = data[pos+8:pos+24].split(b'\x00')[0].decode('ascii')
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', data, pos+24)
            nsects = struct.unpack_from('<I', data, pos+64)[0]
            actual_fileoff = fileoff + base if base > 0 else fileoff
            seg = Segment(segname, vmaddr, vmsize, actual_fileoff, filesize)
            segments.append(seg)
            # Parse sections
            sec_pos = pos + 72
            for _ in range(nsects):
                sname = data[sec_pos:sec_pos+16].split(b'\x00')[0].decode('ascii')
                ssegname = data[sec_pos+16:sec_pos+32].split(b'\x00')[0].decode('ascii')
                saddr, ssize = struct.unpack_from('<QQ', data, sec_pos+32)
                soffset = struct.unpack_from('<I', data, sec_pos+48)[0]
                all_sections.append(Section(sname, ssegname, saddr, ssize, soffset))
                sec_pos += 80
        pos += cmdsize

    return segments, base, all_sections

# ─── Discovery file parser ────────────────────────────────────────────

class MethodInfo:
    def __init__(self, name, argc, unslid_va, prologue_bytes):
        self.name = name
        self.argc = argc
        self.unslid_va = unslid_va
        self.prologue_bytes = prologue_bytes

def parse_discovery(path):
    """Parse hook_discovery.txt produced by DIAG mode."""
    methods = []
    segments = {}
    image_path = None

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('IMAGE_PATH='):
                image_path = line.split('=', 1)[1]
            elif line.startswith('SEG '):
                # SEG __TEXT VMADDR=0x... VMSIZE=0x... FILEOFF=0x... FILESIZE=0x...
                parts = line.split()
                segname = parts[1]
                props = {}
                for p in parts[2:]:
                    k, v = p.split('=')
                    props[k] = int(v, 16)
                segments[segname] = props
            elif line.startswith('METHOD '):
                parts = line.split()
                name = parts[1]
                if 'NOTFOUND' in line or 'NOFP' in line:
                    print(f"  WARNING: {name} not found in discovery")
                    continue
                argc = int(parts[2].split('=')[1])
                unslid = int(parts[4].split('=')[1], 16)
                byteshex = parts[5].split('=')[1]
                raw = bytes.fromhex(byteshex)
                methods.append(MethodInfo(name, argc, unslid, raw))

    return methods, segments, image_path

# ─── Code cave finder ─────────────────────────────────────────────────

def find_code_cave(data, text_seg, min_size):
    """Find a block of zeros in __TEXT large enough for our stubs."""
    start = text_seg.fileoff
    end = start + text_seg.filesize
    best_offset = -1
    best_size = 0

    # Scan backwards from end of __TEXT (alignment padding is usually there)
    run_start = -1
    run_len = 0

    for i in range(end - 4, start, -4):
        word = struct.unpack_from('<I', data, i)[0]
        if word == 0x00000000 or word == 0xD503201F:  # zeros or NOPs
            if run_start < 0:
                run_start = i
            run_len += 4
        else:
            if run_len >= min_size and run_len > best_size:
                best_offset = run_start - run_len + 4
                best_size = run_len
            run_start = -1
            run_len = 0

    if run_len >= min_size and run_len > best_size:
        best_offset = run_start - run_len + 4
        best_size = run_len

    return best_offset, best_size

def find_data_cave(data, data_seg, min_size, sections):
    """Find unused space in __DATA that doesn't overlap any section."""
    seg_file_end = data_seg.fileoff + data_seg.filesize

    # Find the end of the last file-backed section in this segment.
    last_section_end = data_seg.fileoff
    for sec in sections:
        if sec.segname.startswith('__DATA') and sec.offset > 0:
            sec_end = sec.offset + sec.size
            if sec_end > last_section_end:
                last_section_end = sec_end
                print("    last file-backed section: %s ends at 0x%x" % (sec.name, sec_end))

    # Start after the last section, aligned to 8 bytes.
    cave_start = (last_section_end + 7) & ~7
    avail = seg_file_end - cave_start

    if avail >= min_size:
        return cave_start, avail
    return -1, 0

# ─── Patcher ──────────────────────────────────────────────────────────

def va_to_fileoff(va, segments, fat_base):
    """Convert an unslid virtual address to a file offset."""
    for seg in segments:
        if seg.vmaddr <= va < seg.vmaddr + seg.vmsize:
            return (va - seg.vmaddr) + seg.fileoff
    raise ValueError(f"VA 0x{va:x} not in any segment")

def fileoff_to_va(fileoff, segments, fat_base):
    """Convert a file offset to an unslid virtual address."""
    for seg in segments:
        if seg.fileoff <= fileoff < seg.fileoff + seg.filesize:
            return (fileoff - seg.fileoff) + seg.vmaddr
    raise ValueError(f"File offset 0x{fileoff:x} not in any segment")

def patch_binary(binary_path, discovery_path, output_path):
    print(f"[*] Loading binary: {binary_path}")
    with open(binary_path, 'rb') as f:
        data = bytearray(f.read())

    print(f"[*] Parsing discovery: {discovery_path}")
    methods, disc_segs, image_path = parse_discovery(discovery_path)
    if not methods:
        print("[!] No methods found in discovery file")
        return False

    print(f"[*] Found {len(methods)} methods to patch")
    for m in methods:
        print(f"    {m.name}: unslid VA=0x{m.unslid_va:x}")

    print("[*] Parsing Mach-O segments")
    segments, fat_base, sections = parse_macho_segments(data)
    for seg in segments:
        print(f"    {seg.name:16s} vmaddr=0x{seg.vmaddr:x} fileoff=0x{seg.fileoff:x} size=0x{seg.filesize:x}")

    text_seg = next((s for s in segments if s.name == '__TEXT'), None)
    data_seg = next((s for s in segments if s.name == '__DATA'), None)
    if not text_seg:
        # Try __DATA_CONST or other data segments
        data_seg = next((s for s in segments if s.name.startswith('__DATA')), None)
    if not text_seg or not data_seg:
        print("[!] Cannot find __TEXT or __DATA segment")
        return False

    # Verify method prologues match what's in the binary
    for m in methods:
        foff = va_to_fileoff(m.unslid_va, segments, fat_base)
        actual = data[foff:foff+32]
        if actual != m.prologue_bytes:
            print(f"[!] WARNING: {m.name} prologue mismatch at fileoff 0x{foff:x}")
            print(f"    Discovery: {m.prologue_bytes.hex()}")
            print(f"    Binary:    {actual.hex()}")
            # Non-fatal — the binary might have been updated, but we'll use what's in the binary
        else:
            print(f"[+] {m.name}: prologue verified at fileoff 0x{foff:x}")

    # Each method needs:
    #   Trampoline: 5 instructions (20 bytes)
    #   Orig stub: 2 instructions (8 bytes)
    # Total per method: 28 bytes, round up to 32 for alignment
    # Plus hookslot table: 16 (magic) + 4*8 (hookslots) + 4*8 (origVAs) = 80 bytes
    num_methods = len(methods)
    cave_need = num_methods * 32
    data_need = 16 + num_methods * 16  # magic + hookslots + origVAs

    print(f"[*] Need {cave_need} bytes code cave, {data_need} bytes data")

    cave_off, cave_avail = find_code_cave(data, text_seg, cave_need)
    if cave_off < 0:
        print(f"[!] Cannot find code cave in __TEXT ({cave_need} bytes needed)")
        return False
    print(f"[+] Code cave at fileoff 0x{cave_off:x} ({cave_avail} bytes available)")

    dcave_off, dcave_avail = find_data_cave(data, data_seg, data_need, sections)
    if dcave_off < 0:
        print(f"[!] Cannot find data cave in __DATA ({data_need} bytes needed)")
        return False
    print(f"[+] Data cave at fileoff 0x{dcave_off:x} ({dcave_avail} bytes available)")

    # Layout the hookslot table in __DATA
    hookslot_table_off = dcave_off
    hookslot_table_va = fileoff_to_va(hookslot_table_off, segments, fat_base)

    # Write magic
    struct.pack_into('<Q', data, hookslot_table_off, HOOKSLOT_MAGIC0)
    struct.pack_into('<Q', data, hookslot_table_off + 8, HOOKSLOT_MAGIC1)

    # Hookslot entries start at offset 16 from magic
    hookslots_off = hookslot_table_off + 16
    origvas_off = hookslots_off + num_methods * 8

    # For each unused slot (up to 4), initialize to zero
    for i in range(4):
        struct.pack_into('<Q', data, hookslots_off + i * 8, 0)
        struct.pack_into('<Q', data, origvas_off + i * 8, 0)

    # Now patch each method
    tramp_cursor = cave_off
    for i, m in enumerate(methods):
        target_foff = va_to_fileoff(m.unslid_va, segments, fat_base)
        target_va = m.unslid_va

        # Save original first instruction
        orig_insn = struct.unpack_from('<I', data, target_foff)[0]

        # ── Build trampoline ──
        tramp_va = fileoff_to_va(tramp_cursor, segments, fat_base)
        hookslot_va = fileoff_to_va(hookslots_off + i * 8, segments, fat_base)

        # Instruction 0: ADRP X16, hookslot@PAGE
        insn0 = encode_adrp(16, tramp_va, hookslot_va)
        # Instruction 1: LDR X16, [X16, hookslot@PAGEOFF]
        insn1 = encode_ldr_x_uoff(16, 16, hookslot_va & 0xFFF)
        # Instruction 2: CBNZ X16, +8 (skip 1 insn to BR)
        insn2 = encode_cbnz_x(16, 8)
        # Instruction 3: B orig_stub (filled in after we know orig_stub location)
        orig_stub_off = tramp_cursor + 20  # right after the 5 trampoline insns, rounded
        orig_stub_va = fileoff_to_va(orig_stub_off, segments, fat_base)
        insn3_offset = orig_stub_va - (tramp_va + 12)  # PC at insn3 = tramp_va + 12
        insn3 = encode_b(insn3_offset)
        # Instruction 4: BR X16
        insn4 = encode_br(16)

        # Write trampoline
        struct.pack_into('<I', data, tramp_cursor + 0, insn0)
        struct.pack_into('<I', data, tramp_cursor + 4, insn1)
        struct.pack_into('<I', data, tramp_cursor + 8, insn2)
        struct.pack_into('<I', data, tramp_cursor + 12, insn3)
        struct.pack_into('<I', data, tramp_cursor + 16, insn4)

        # ── Build orig stub ──
        # Instruction 0: <original saved instruction>
        # Instruction 1: B <target + 4>
        b_back_offset = (target_va + 4) - (orig_stub_va + 4)  # PC at insn1 = orig_stub_va + 4
        insn_orig0 = orig_insn
        insn_orig1 = encode_b(b_back_offset)

        struct.pack_into('<I', data, orig_stub_off + 0, insn_orig0)
        struct.pack_into('<I', data, orig_stub_off + 4, insn_orig1)

        # ── Write orig stub VA to hookslot table ──
        struct.pack_into('<Q', data, origvas_off + i * 8, orig_stub_va)

        # ── Patch target function prologue ──
        # Replace first instruction with: B <trampoline>
        b_to_tramp = tramp_va - target_va
        patch_insn = encode_b(b_to_tramp)
        struct.pack_into('<I', data, target_foff, patch_insn)

        # Advance cursor (28 bytes used, align to 32)
        tramp_cursor = orig_stub_off + 8
        # Align to 4 bytes (already is, but be safe)
        tramp_cursor = (tramp_cursor + 3) & ~3

        print(f"[+] Patched {m.name}:")
        print(f"    target     VA=0x{target_va:x} fileoff=0x{target_foff:x}")
        print(f"    trampoline VA=0x{tramp_va:x} fileoff=0x{tramp_cursor - 28:x}")
        print(f"    orig_stub  VA=0x{orig_stub_va:x}")
        print(f"    hookslot   VA=0x{hookslot_va:x}")
        print(f"    saved_insn 0x{orig_insn:08x}")

    # Write output
    print(f"[*] Writing patched binary: {output_path}")
    with open(output_path, 'wb') as f:
        f.write(data)

    print(f"[+] Done! {len(methods)} methods patched.")
    print()
    print("Next steps:")
    print("  1. Replace the binary in the IPA with this patched version")
    print("  2. Set hook_config.txt to 'HOOKSLOT'")
    print("  3. Sideload the IPA (re-signing bakes in the patches)")
    print("  4. Hooks will activate automatically")
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 offline_patcher.py <macho_binary> <hook_discovery.txt> [output]")
        print()
        print("  macho_binary     - Path to the CoinMaster Mach-O executable")
        print("  hook_discovery.txt - Discovery file from DIAG mode")
        print("  output           - Output path (default: <binary>.patched)")
        sys.exit(1)

    binary_path = sys.argv[1]
    discovery_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else binary_path + '.patched'

    if not os.path.exists(binary_path):
        print(f"[!] Binary not found: {binary_path}")
        sys.exit(1)
    if not os.path.exists(discovery_path):
        print(f"[!] Discovery file not found: {discovery_path}")
        sys.exit(1)

    success = patch_binary(binary_path, discovery_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
