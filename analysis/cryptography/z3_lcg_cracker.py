from z3 import *
import time

def solve_java_lcg(bucket_sequence, num_buckets=6):
    """
    Attempt to crack the state of a Java LCG given a sequence of bucketed outcomes.
    
    In Java, the internal LCG state updates as:
       S_{i+1} = (S_i * 25214903917 + 11) mod 2^48
    
    Normally nextInt(n) bounds the output roughly equivalent to taking the
    top 31 bits and performing modulo n.
    
    Here we assume the server computes: 
       output = (state_i >> 17) % num_buckets
    and returns a specific symbol array index (e.g. 0=Accum, 1=Coin, etc.)
    
    If we feed it 10-20 consecutive buckets, it can usually lock down the 48-bit state.
    """
    print(f"Initializing Z3 solver with sequence of {len(bucket_sequence)} outcomes...")
    
    # 1. Initialize Z3 Theorem Solver
    solver = Solver()
    
    # 2. Define the exact unknown: the 48-bit initial seed
    # We use a BitVec (Bit Vector) in Z3 to model actual hardware bit-shifts accurately
    S0 = BitVec('S0', 48)
    
    # LCG constants for Java java.util.Random
    MULTIPLIER = 25214903917 # 0x5DEECE66D
    ADDEND = 11
    MASK = (1 << 48) - 1
    
    current_state = S0
    
    # 3. Apply the conditions for every spin we observed
    print("Building constraint equations...")
    for i, observed_bucket in enumerate(bucket_sequence):
        # Step the PRNG forward mathematically
        current_state = (current_state * MULTIPLIER + ADDEND) & MASK
        
        # Take the top 31 bits (pseudo-output)
        # Shift right by 17 bits to match Java's next() logic
        output_bits = LShR(current_state, 17)
        
        # In this simple proof-of-concept, we assume a direct modulo
        # (output_bits) % num_buckets == observed_bucket
        # Note: Z3 handles BitVec modulo natively (URem for unsigned remainder)
        solver.add(URem(output_bits, num_buckets) == observed_bucket)

    print("Solving for the 48-bit Internal Master Seed... (may take seconds to minutes)")
    start_time = time.time()
    
    # 4. Check if Z3 can find a valid master seed that causes all outputs to perfectly match
    result = solver.check()
    
    if result == sat:
        model = solver.model()
        cracked_seed = model[S0].as_long()
        print(f"\n[+] CRACKED! Found valid internal Server PRNG State: {cracked_seed}")
        print(f"[+] Time taken: {time.time() - start_time:.2f} seconds")
        
        # Forward generation proof
        print("\nVerifying by generating the next 5 spins from this seed:")
        test_state = cracked_seed
        for x in range(5):
            test_state = (test_state * MULTIPLIER + ADDEND) & MASK
            val = (test_state >> 17) % num_buckets
            print(f"  Future Spin {x+1}: Bucket {val}")
            
    elif result == unsat:
        print("\n[-] UNSAT (No possible seed exists).")
        print("    This means either:")
        print("    1. The sequence jumped (other players spun the same PRNG instance)")
        print("    2. The server uses a different PRNG (e.g. MT19937 or CSPRNG)")
        print("    3. The probability mapping is more complex than simple modulo")
    else:
        print("\n[?] UNKNOWN (Solver timed out or gave up).")

if __name__ == '__main__':
    # Proof of concept: Suppose the server generated these 15 consecutive outcomes
    # on a user-isolated Java Random instance with nextInt(6).
    # Since we only get bucket outcomes (0-5), normally we have immense entropy loss.
    # But Z3 can brute force the constraints backwards.
    
    # Fake sequence generated from seed 99999999 for demonstration
    example_sequence = [5, 1, 3, 4, 0, 5, 2, 4, 1, 0, 3, 5, 2, 0, 1] 
    
    solve_java_lcg(example_sequence)
