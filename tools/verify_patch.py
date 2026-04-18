#!/usr/bin/env python3
"""Verify the patched UnityFramework binary."""
import struct, sys

HOOKSLOT_MAGIC0 = 0xDEADBEEF5350494E
HOOKSLOT_MAGIC1 = 0x484F4F4B534C4F54

# Target method unslid VAs from discovery
METHODS = {
    'OnSpinResultReceived':       0x2e760c8,
    'SetFreezeResolve':           0x2e7049c,
    'activateWinSequence':        0x2e79914,
    'ContainsAccumulationResult': 0x2e77590,
}

# Original prologues (first 4 bytes only)
ORIG_PROLOGUES = {
    'OnSpinResultReceived':       bytes.fromhex('ff4303d1'),
    'SetFreezeResolve':           bytes.fromhex('f657bda9'),
    'activateWinSequence':        bytes.fromhex('ff8302d1'),
    'ContainsAccumulationResult': bytes.fromhex('ff0301d1'),
}

def decode_b(insn):
    """Decode B instruction, return target offset in bytes."""
    if (insn >> 26) != 0x05:  # B = 000101
        return None
    imm26 = insn & 0x3FFFFFF
    if imm26 & 0x2000000:  # sign extend
        imm26 |= ~0x3FFFFFF
    return imm26 << 2

def decode_adrp(insn):
    """Decode ADRP, return (rd, imm in pages)."""
    if (insn & 0x9F000000) != 0x90000000:
        return None
    rd = insn & 0x1F
    immlo = (insn >> 29) & 0x3
    immhi = (insn >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & 0x100000:  # sign extend 21-bit
        imm -= 0x200000
    return rd, imm

def decode_ldr_uoff(insn):
    """Decode LDR Xt, [Xn, #uoff]."""
    if (insn & 0xFFC00000) != 0xF9400000:
        return None
    rt = insn & 0x1F
    rn = (insn >> 5) & 0x1F
    imm12 = (insn >> 10) & 0xFFF
    return rt, rn, imm12 * 8  # scale by 8 for 64-bit

def decode_cbnz(insn):
    """Decode CBNZ Xt."""
    if (insn & 0xFF000000) != 0xB5000000:
        return None
    rt = insn & 0x1F
    imm19 = (insn >> 5) & 0x7FFFF
    if imm19 & 0x40000:
        imm19 -= 0x80000
    return rt, imm19 << 2

def decode_br(insn):
    """Decode BR Xn."""
    if (insn & 0xFFFFFC1F) != 0xD61F0000:
        return None
    rn = (insn >> 5) & 0x1F
    return rn

with open(sys.argv[1], 'rb') as f:
    data = f.read()

# Parse segments (thin binary assumed since vmaddr==fileoff from discovery)
magic = struct.unpack_from('<I', data, 0)[0]
print("Magic: 0x%08x" % magic)
assert magic == 0xFEEDFACF, "Expected thin Mach-O"

ncmds = struct.unpack_from('<I', data, 16)[0]
pos = 32
segments = {}
sections_list = []
for _ in range(ncmds):
    cmd, cmdsize = struct.unpack_from('<II', data, pos)
    if cmd == 0x19:  # LC_SEGMENT_64
        name = data[pos+8:pos+24].split(b'\x00')[0].decode()
        vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', data, pos+24)
        nsects = struct.unpack_from('<I', data, pos+64)[0]
        segments[name] = (vmaddr, vmsize, fileoff, filesize)
        sec_pos = pos + 72
        for si in range(nsects):
            sname = data[sec_pos:sec_pos+16].split(b'\x00')[0].decode()
            ssegname = data[sec_pos+16:sec_pos+32].split(b'\x00')[0].decode()
            saddr, ssize = struct.unpack_from('<QQ', data, sec_pos+32)
            soffset = struct.unpack_from('<I', data, sec_pos+48)[0]
            sections_list.append((sname, ssegname, saddr, ssize, soffset))
            sec_pos += 80
    pos += cmdsize

print("\n=== Segments ===")
for name, (va, vsz, fo, fsz) in segments.items():
    print("  %-16s va=0x%08x vsz=0x%x fo=0x%08x fsz=0x%x" % (name, va, vsz, fo, fsz))

print("\n=== __DATA sections ===")
for sname, sseg, saddr, ssize, soff in sections_list:
    if sseg.startswith('__DATA'):
        end = soff + ssize if soff > 0 else saddr + ssize
        print("  %s.%-24s addr=0x%08x size=0x%x foff=0x%08x end=0x%08x" % (sseg, sname, saddr, ssize, soff, end))

# Check each method's prologue
print("\n=== Method prologues (should be B instructions) ===")
for name, va in sorted(METHODS.items(), key=lambda x: x[1]):
    foff = va  # vmaddr == fileoff for this binary
    insn = struct.unpack_from('<I', data, foff)[0]
    b_off = decode_b(insn)
    orig = ORIG_PROLOGUES[name]
    orig_insn = struct.unpack_from('<I', orig, 0)[0]

    if b_off is not None:
        tramp_va = va + b_off
        print("  %s: 0x%08x -> B %+d -> tramp VA=0x%x OK" % (name, insn, b_off, tramp_va))

        # Verify trampoline
        tramp_foff = tramp_va  # vmaddr == fileoff
        if tramp_foff < 0 or tramp_foff + 20 > len(data):
            print("    TRAMPOLINE OUT OF BOUNDS!")
            continue
        t = [struct.unpack_from('<I', data, tramp_foff + i*4)[0] for i in range(5)]
        print("    tramp insns: %s" % ' '.join('0x%08x' % x for x in t))

        # Decode trampoline
        adrp = decode_adrp(t[0])
        ldr = decode_ldr_uoff(t[1])
        cbnz = decode_cbnz(t[2])
        b_orig = decode_b(t[3])
        br = decode_br(t[4])

        ok = True
        if adrp:
            rd, imm_pages = adrp
            hookslot_page = (tramp_va & ~0xFFF) + (imm_pages << 12)
            if ldr:
                rt, rn, uoff = ldr
                hookslot_va = hookslot_page + uoff
                print("    ADRP X%d + LDR X%d,[X%d,#0x%x] -> hookslot VA=0x%x" % (rd, rt, rn, uoff, hookslot_va))
                if hookslot_va < len(data):
                    hs_val = struct.unpack_from('<Q', data, hookslot_va)[0]
                    print("    hookslot value: 0x%x (should be 0)" % hs_val)
                else:
                    print("    hookslot VA OUT OF FILE BOUNDS!")
                    ok = False
            else:
                print("    LDR decode FAILED: 0x%08x" % t[1])
                ok = False
        else:
            print("    ADRP decode FAILED: 0x%08x" % t[0])
            ok = False

        if cbnz:
            rt, off = cbnz
            print("    CBNZ X%d, +%d" % (rt, off))
        else:
            print("    CBNZ decode FAILED: 0x%08x" % t[2])
            ok = False

        if b_orig is not None:
            orig_stub_va = (tramp_va + 12) + b_orig
            print("    B orig_stub VA=0x%x" % orig_stub_va)
            # Verify orig stub
            os_foff = orig_stub_va
            if os_foff >= 0 and os_foff + 8 <= len(data):
                os0 = struct.unpack_from('<I', data, os_foff)[0]
                os1 = struct.unpack_from('<I', data, os_foff + 4)[0]
                match0 = "OK" if os0 == orig_insn else "MISMATCH! got 0x%08x expected 0x%08x" % (os0, orig_insn)
                print("    orig_stub[0]: 0x%08x %s" % (os0, match0))
                b_back = decode_b(os1)
                if b_back is not None:
                    back_target = (orig_stub_va + 4) + b_back
                    expected_back = va + 4
                    match1 = "OK" if back_target == expected_back else "MISMATCH! got 0x%x expected 0x%x" % (back_target, expected_back)
                    print("    orig_stub[1]: B -> 0x%x %s" % (back_target, match1))
                else:
                    print("    orig_stub[1]: NOT A B INSTRUCTION: 0x%08x" % os1)
                    ok = False
            else:
                print("    orig_stub OUT OF BOUNDS!")
                ok = False
        else:
            print("    B orig_stub decode FAILED: 0x%08x" % t[3])
            ok = False

        if br is not None:
            print("    BR X%d" % br)
        else:
            print("    BR decode FAILED: 0x%08x" % t[4])
            ok = False

        if ok:
            print("    === ALL CHECKS PASSED ===")
        else:
            print("    === SOME CHECKS FAILED ===")
    elif insn == orig_insn:
        print("  %s: 0x%08x -> UNPATCHED (original prologue)" % (name, insn))
    else:
        print("  %s: 0x%08x -> UNKNOWN (not B, not original)" % (name, insn))

# Find and verify hookslot table
print("\n=== Hookslot table search ===")
data_va, data_vsz, data_fo, data_fsz = segments['__DATA']
found_magic = False
for off in range(data_fo, data_fo + data_fsz - 16, 8):
    v0 = struct.unpack_from('<Q', data, off)[0]
    if v0 == HOOKSLOT_MAGIC0:
        v1 = struct.unpack_from('<Q', data, off + 8)[0]
        if v1 == HOOKSLOT_MAGIC1:
            found_magic = True
            print("  Magic found at fileoff 0x%x (VA 0x%x)" % (off, off))
            for i in range(4):
                hs = struct.unpack_from('<Q', data, off + 16 + i*8)[0]
                ov = struct.unpack_from('<Q', data, off + 48 + i*8)[0]
                print("    slot[%d]: hookslot=0x%x origVA=0x%x" % (i, hs, ov))
            # Check what's around the magic
            prev8 = data[off-8:off]
            next_after = data[off+80:off+88]
            print("  8 bytes before magic: %s" % prev8.hex())
            print("  8 bytes after table: %s" % next_after.hex())
            break
if not found_magic:
    print("  HOOKSLOT MAGIC NOT FOUND IN __DATA!")

# Check the __LINKEDIT vs data cave
print("\n=== Segment boundary check ===")
linkedit = segments.get('__LINKEDIT')
if linkedit:
    le_va, le_vsz, le_fo, le_fsz = linkedit
    print("  __LINKEDIT fo=0x%x end=0x%x" % (le_fo, le_fo + le_fsz))
    print("  __DATA     fo=0x%x end=0x%x" % (data_fo, data_fo + data_fsz))
    if data_fo + data_fsz > le_fo:
        print("  WARNING: __DATA file region overlaps __LINKEDIT!")
    else:
        print("  Gap between __DATA file end and __LINKEDIT: %d bytes" % (le_fo - (data_fo + data_fsz)))

# Check code cave region
print("\n=== Code cave region ===")
text_va, text_vsz, text_fo, text_fsz = segments['__TEXT']
text_end = text_fo + text_fsz
for i in range(text_end - 4, text_end - 8192, -4):
    w = struct.unpack_from('<I', data, i)[0]
    if w != 0:
        print("  Last non-zero in __TEXT at foff 0x%x: 0x%08x" % (i, w))
        print("  Cave starts at 0x%x, %d bytes to end of __TEXT" % (i+4, text_end - i - 4))
        # Show the non-zero word context
        print("  Words around cave start:")
        for j in range(max(0, i-16), min(len(data), i+32), 4):
            ww = struct.unpack_from('<I', data, j)[0]
            marker = " <-- last code" if j == i else ""
            print("    0x%08x: 0x%08x%s" % (j, ww, marker))
        break

print("\n=== File size check ===")
print("  File size: %d bytes (0x%x)" % (len(data), len(data)))
if linkedit:
    expected_end = le_fo + le_fsz
    print("  Expected end (__LINKEDIT): 0x%x" % expected_end)
    if len(data) < expected_end:
        print("  WARNING: File truncated!")
    elif len(data) > expected_end:
        print("  Extra data after __LINKEDIT: %d bytes" % (len(data) - expected_end))
