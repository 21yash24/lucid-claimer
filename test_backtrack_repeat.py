"""
test_backtrack_repeat.py
------------------------
Validates backtracking constraint-satisfaction performance when allowing
repeating characters from the alphanumeric set (digits + uppercase A-Z).
"""

import random
import string
import time
from typing import List, Tuple, Optional

CHAR_SET = string.digits + string.ascii_uppercase  # '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def get_feedback(guess: str, secret: str) -> Tuple[int, int]:
    correct_spot = sum(1 for g, s in zip(guess, secret) if g == s)
    guess_unmatched = [g for g, s in zip(guess, secret) if g != s]
    secret_unmatched = [s for g, s in zip(guess, secret) if g != s]
    wrong_spot = 0
    for char in guess_unmatched:
        if char in secret_unmatched:
            wrong_spot += 1
            secret_unmatched.remove(char)
    return correct_spot, wrong_spot

def find_candidate_backtrack(history: List[Tuple[str, int, int]]) -> Optional[str]:
    h_processed = []
    for g, c, w in history:
        # Pre-calculate counts of each character in guess for fast overlap bounds checking
        g_counts = {}
        for char in g:
            g_counts[char] = g_counts.get(char, 0) + 1
        h_processed.append((list(g), c, w, g, g_counts))
        
    chars = list(CHAR_SET)
    
    # Pre-shuffle lists for each position to try different characters
    depth_chars = []
    for _ in range(5):
        dc = chars[:]
        random.shuffle(dc)
        depth_chars.append(dc)
        
    candidate = [''] * 5

    def is_consistent_fast(cand_str: str) -> bool:
        for g_list, correct, wrong, _, _ in h_processed:
            c_spot = 0
            w_spot = 0
            g_unmatched = []
            c_unmatched = []
            
            for i in range(5):
                if cand_str[i] == g_list[i]:
                    c_spot += 1
                else:
                    g_unmatched.append(g_list[i])
                    c_unmatched.append(cand_str[i])
            
            if c_spot != correct:
                return False
                
            for char in g_unmatched:
                if char in c_unmatched:
                    w_spot += 1
                    c_unmatched.remove(char)
            
            if w_spot != wrong:
                return False
        return True

    def backtrack(depth: int) -> Optional[str]:
        if depth == 5:
            cand_str = "".join(candidate)
            if is_consistent_fast(cand_str):
                return cand_str
            return None
        
        # Current candidate prefix counts for overlap bounds
        pref_counts = {}
        for i in range(depth):
            pref_counts[candidate[i]] = pref_counts.get(candidate[i], 0) + 1
            
        remaining = 4 - depth
        
        for c in depth_chars[depth]:
            candidate[depth] = c
            
            # Update prefix counts temporarily
            pref_counts[c] = pref_counts.get(c, 0) + 1
            
            possible = True
            for g_list, correct, wrong, _, g_counts in h_processed:
                # 1. Exact matches check
                matches = 0
                for i in range(depth + 1):
                    if candidate[i] == g_list[i]:
                        matches += 1
                        
                if matches > correct:
                    possible = False
                    break
                if matches + remaining < correct:
                    possible = False
                    break
                
                # 2. Overlap bounds check (handles repeating characters)
                min_overlap = 0
                for char, count in pref_counts.items():
                    if char in g_counts:
                        min_overlap += min(count, g_counts[char])
                        
                if min_overlap > (correct + wrong):
                    possible = False
                    break
                if min_overlap + remaining < (correct + wrong):
                    possible = False
                    break
            
            if possible:
                res = backtrack(depth + 1)
                if res:
                    return res
                    
            # Revert prefix counts
            pref_counts[c] -= 1
            if pref_counts[c] == 0:
                del pref_counts[c]
                
        return None
        
    return backtrack(0)

def main():
    # Simulation: choose a secret with repeating characters
    secret = "WAWA9"
    print(f"Secret: {secret}")
    
    # Simulating a round-by-round Mastermind solve
    history = []
    guess = "12345"
    
    for r in range(1, 8):
        c, w = get_feedback(guess, secret)
        history.append((guess, c, w))
        print(f"Round {r}: Guess={guess} -> Correct={c}, Partial={w}")
        
        if c == 5:
            print("Solved!")
            break
            
        t0 = time.perf_counter()
        next_guess = find_candidate_backtrack(history)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  Generated next guess in {elapsed:.2f}ms: {next_guess}")
        guess = next_guess

if __name__ == "__main__":
    main()
