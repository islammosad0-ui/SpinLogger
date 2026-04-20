"""Disassemble a function from UnityFramework by VA, resolving BL targets via script.json."""
import json
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

BINARY = 'Payload/CoinMaster.app/Frameworks/UnityFramework.framework/UnityFramework'
SCRIPT = 'out/script.json'

def load_name_map():
    with open(SCRIPT, 'r', encoding='utf-8') as f:
        sj = json.load(f)
    return {m['Address']: m['Name'] for m in sj['ScriptMethod']}

def find_next_func(name_map, start_va):
    """Find next known function VA after start_va — used as end bound."""
    candidates = [a for a in name_map if a > start_va and a < start_va + 0x4000]
    return min(candidates) if candidates else start_va + 0x800

def disasm_func(va_start, name_map, data, max_bytes=None):
    end = find_next_func(name_map, va_start) if max_bytes is None else va_start + max_bytes
    code = data[va_start:end]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    print(f'=== {name_map.get(va_start, "?")} @ {hex(va_start)} (size={end - va_start} bytes) ===')
    for ins in md.disasm(code, va_start):
        line = f'0x{ins.address:08x}  {ins.mnemonic:7s} {ins.op_str}'
        if ins.mnemonic in ('bl', 'b') and ins.op_str.startswith('#'):
            try:
                tgt = int(ins.op_str[1:], 16)
                tgt_name = name_map.get(tgt)
                if tgt_name:
                    line += f'   ; {tgt_name}'
            except ValueError:
                pass
        print(line)

def main():
    targets = [int(a, 16) for a in sys.argv[1:]]
    with open(BINARY, 'rb') as f:
        data = f.read()
    name_map = load_name_map()
    for va in targets:
        disasm_func(va, name_map, data)
        print()

if __name__ == '__main__':
    main()
