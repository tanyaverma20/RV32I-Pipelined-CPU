#!/usr/bin/env python3
"""
RV32I Pipelined CPU — RTL Verification & Simulation Infrastructure
Maintainer & Verification Author: Tanya Verma (https://github.com/tanyaverma20/RV32I-Pipelined-CPU)
Base Processor Architecture: Zhiyuan (Jerry) Jiang (Apache-2.0)

Features:
  - 11 Submodule Directed & Constrained-Random Unit Tests
  - 6 Top-Level Pipeline Integration Tests (Phases 1-5 + Universal ISA Regression)
  - 4 Compiled C Benchmarks (hello_world, loop1, loop2, fib)
  - Colorized test execution reporting with execution cycles, stalls, flushes, branch accuracy
  - Machine-readable exit codes (0 for pass, 1 for fail) for CI/CD pipelines
"""

import sys
import os
import time
import argparse
import subprocess

# Ensure MSYS2 UCRT64 tools are available in PATH on Windows if present
if sys.platform == "win32":
    msys_bin = r"C:\msys64\ucrt64\bin"
    if os.path.exists(msys_bin) and msys_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = msys_bin + os.pathsep + os.environ.get("PATH", "")

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

UNIT_MODULES = [
    ("alu", "Arithmetic Logic Unit (10k CRT + Directed)"),
    ("alu_control", "ALU Control Decoder (21 Directed)"),
    ("branch_comp", "Branch Comparator (10k CRT + 16 Directed)"),
    ("control_unit", "Main Control Unit Decoder (12 Directed)"),
    ("data_mem", "Data Memory & Byte Enable Masks (6 Directed)"),
    ("imm_gen", "Immediate Generator - All Types (13 Directed)"),
    ("instruction_mem", "Instruction ROM & Shadow Compare (713 Instructions)"),
    ("load_filter", "Load Data Alignment & Sign Extension (12 Directed)"),
    ("pc", "Program Counter & Pipeline Stall Freeze (5 Directed)"),
    ("reg_file", "Register File & Internal Bypass (1k CRT Torture)"),
    ("store_mask", "Store Data Shift & Byte/Halfword Masks (14 Directed)")
]

CORE_PHASES = [
    ("phase_1", "Phase 1: Basic 5-stage Datapath (NOP Padded)", 1),
    ("phase_2", "Phase 2: EX & MEM RAW Data Forwarding Paths", 1),
    ("phase_3", "Phase 3: Load-Use Hazard Detection & 1-Cycle Stall", 1),
    ("phase_4", "Phase 4: ID Branch Resolution & Pipeline Flush", 1),
    ("phase_5", "Phase 5: Dynamic 2-bit Predictor & 64-Entry BTB", 1),
    ("tb_top_soc", "Universal ISA Self-Checking Comprehensive Suite", 1),
]

BENCHMARKS = [
    ("hello_world", "C Hello World (1 + 2 = 3)", 3, 5000),
    ("loop1", "C Loop 1: 10,000 Iteration Counting Loop", 10000, 100000),
    ("loop2", "C Loop 2: Alternating Branching Pattern", 0, 100000),
    ("fib", "C Fibonacci(15): Recursive Call/Return Stress", 610, 100000),
]


def check_dependencies():
    """Verify iverilog and vvp are available."""
    missing = []
    for tool in ["iverilog", "vvp"]:
        try:
            res = subprocess.run([tool, "-V"], capture_output=True, text=True)
            if res.returncode != 0:
                missing.append(tool)
        except FileNotFoundError:
            missing.append(tool)
    if missing:
        print(f"{RED}[ERROR] Required EDA tools missing: {', '.join(missing)}{RESET}")
        print("Please install Icarus Verilog and ensure 'iverilog' and 'vvp' are in your PATH.")
        sys.exit(1)


def compile_soc_top(waves=False):
    """Compile soc_top DUT and testbench."""
    os.makedirs("sim", exist_ok=True)
    out_vvp = "sim/soc_top_test.vvp"
    rtl_files = [f"rtl/{f}" for f in os.listdir("rtl") if f.endswith(".v")]
    tb_file = "tb/top/tb_soc_top.sv"
    
    cmd = ["iverilog", "-g2012", "-o", out_vvp, tb_file] + rtl_files
    print(f"{CYAN}[BUILD] Compiling SoC Top with Icarus Verilog (-g2012)...{RESET}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{RED}[BUILD FAILED]{RESET}\n{res.stderr}")
        return False
    print(f"{GREEN}[BUILD SUCCESS] Created {out_vvp}{RESET}\n")
    return True


def run_unit_tests():
    """Execute all 11 submodule unit testbenches."""
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{BOLD}{CYAN}                 STAGE 1: SUBMODULE UNIT VERIFICATION                    {RESET}")
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{'Module':18} | {'Description':42} | {'Time':8} | {'Status':8}")
    print("-" * 83)
    
    passed_count = 0
    total_count = len(UNIT_MODULES)
    
    for mod, desc in UNIT_MODULES:
        tb = f"tb/modules/tb_{mod}.sv"
        rtl = f"rtl/{mod}.v"
        out = f"sim/{mod}_test.vvp"
        
        t0 = time.time()
        c_res = subprocess.run(["iverilog", "-g2012", "-o", out, tb, rtl], capture_output=True, text=True)
        if c_res.returncode != 0:
            print(f"{mod:18} | {desc:42} | {'-':8} | {RED}COMPILE FAIL{RESET}")
            continue
            
        r_res = subprocess.run(["vvp", out], capture_output=True, text=True)
        dt = time.time() - t0
        
        has_fatal = "$fatal" in r_res.stdout or "Error:" in r_res.stdout
        is_success = r_res.returncode == 0 and not has_fatal and ("successful" in r_res.stdout or "passed" in r_res.stdout or "All" in r_res.stdout)
        
        status_str = f"{GREEN}PASS{RESET}" if is_success else f"{RED}FAIL{RESET}"
        if is_success:
            passed_count += 1
        print(f"{mod:18} | {desc:42} | {dt:6.2f}s | {status_str}")
        
    print("-" * 83)
    print(f"Submodule Summary: {passed_count}/{total_count} Passed ({100.0 * passed_count / total_count:.1f}%)\n")
    return passed_count == total_count


def run_core_tests(waves=False):
    """Execute top-level pipeline phase integration tests."""
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{BOLD}{CYAN}               STAGE 2: PIPELINED CPU CORE INTEGRATION TESTS             {RESET}")
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{'Test':12} | {'Cycles':8} | {'Stalls':7} | {'Flushes':8} | {'Branches':9} | {'Accuracy':9} | {'Status':8}")
    print("-" * 75)
    
    passed_count = 0
    total_count = len(CORE_PHASES)
    
    for test_id, desc, exp_x10 in CORE_PHASES:
        hex_file = f"tb/programs/{test_id}.hex"
        if not os.path.exists(hex_file):
            print(f"{test_id:12} | Missing {hex_file} | {RED}FAIL{RESET}")
            continue
            
        cmd = ["vvp", "sim/soc_top_test.vvp", f"+HEX={hex_file}", f"+EXPECT_X10={exp_x10}"]
        if waves:
            cmd.append("+WAVES")
            
        res = subprocess.run(cmd, capture_output=True, text=True)
        cycles = stalls = flushes = branches = acc = "N/A"
        
        for line in res.stdout.splitlines():
            if "Total Elapsed Cycles" in line:
                cycles = line.split(":")[-1].strip()
            elif "Stall Cycles Inserted" in line:
                stalls = line.split(":")[-1].strip()
            elif "Flush Cycles Triggered" in line:
                flushes = line.split(":")[-1].strip()
            elif "Branches Resolved" in line:
                branches = line.split(":")[-1].strip()
            elif "Branch Predict Accuracy" in line:
                acc = line.split(":")[-1].strip()
                
        is_pass = "[PASS]" in res.stdout
        status_str = f"{GREEN}PASS{RESET}" if is_pass else f"{RED}FAIL{RESET}"
        if is_pass:
            passed_count += 1
            
        print(f"{test_id:12} | {cycles:8} | {stalls:7} | {flushes:8} | {branches:9} | {acc:9} | {status_str}")
        
    print("-" * 75)
    print(f"Core Integration Summary: {passed_count}/{total_count} Passed ({100.0 * passed_count / total_count:.1f}%)\n")
    return passed_count == total_count


def run_benchmark_tests(waves=False):
    """Execute compiled C benchmark tests."""
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{BOLD}{CYAN}               STAGE 3: COMPILED C BENCHMARKS & WORKLOADS                {RESET}")
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{'Benchmark':12} | {'Cycles':8} | {'Stalls':7} | {'Flushes':8} | {'Accuracy':9} | {'Result (x10)':12} | {'Status':8}")
    print("-" * 80)
    
    passed_count = 0
    total_count = len(BENCHMARKS)
    
    for bench_id, desc, exp_x10, max_c in BENCHMARKS:
        hex_file = f"tb/programs/{bench_id}.hex"
        if not os.path.exists(hex_file):
            print(f"{bench_id:12} | Missing {hex_file} | {RED}FAIL{RESET}")
            continue
            
        cmd = ["vvp", "sim/soc_top_test.vvp", f"+HEX={hex_file}", f"+EXPECT_X10={exp_x10}"]
        if waves:
            cmd.append("+WAVES")
            
        res = subprocess.run(cmd, capture_output=True, text=True)
        cycles = stalls = flushes = acc = ret_code = "N/A"
        
        for line in res.stdout.splitlines():
            if "Total Elapsed Cycles" in line:
                cycles = line.split(":")[-1].strip()
            elif "Stall Cycles Inserted" in line:
                stalls = line.split(":")[-1].strip()
            elif "Flush Cycles Triggered" in line:
                flushes = line.split(":")[-1].strip()
            elif "Branch Predict Accuracy" in line:
                acc = line.split(":")[-1].strip()
            elif "Return Code Register x10" in line:
                ret_code = line.split(":")[-1].strip().split()[0]
                
        is_pass = "[PASS]" in res.stdout
        status_str = f"{GREEN}PASS{RESET}" if is_pass else f"{RED}FAIL{RESET}"
        if is_pass:
            passed_count += 1
            
        result_display = f"{ret_code} (exp {exp_x10})"
        print(f"{bench_id:12} | {cycles:8} | {stalls:7} | {flushes:8} | {acc:9} | {result_display:12} | {status_str}")
        
    print("-" * 80)
    print(f"Benchmark Summary: {passed_count}/{total_count} Passed ({100.0 * passed_count / total_count:.1f}%)\n")
    return passed_count == total_count


def main():
    parser = argparse.ArgumentParser(description="RV32I-Pipelined-CPU Full Verification Suite")
    parser.add_argument("--all", action="store_true", help="Run submodules, core integration, and benchmarks")
    parser.add_argument("--unit", action="store_true", help="Run only submodule unit tests")
    parser.add_argument("--core", action="store_true", help="Run only core integration phase tests")
    parser.add_argument("--benchmarks", action="store_true", help="Run only compiled C benchmarks")
    parser.add_argument("--waves", action="store_true", help="Enable VCD waveform dump")
    args = parser.parse_args()

    check_dependencies()
    
    run_all = args.all or (not args.unit and not args.core and not args.benchmarks)
    
    t_start = time.time()
    all_ok = True
    
    if run_all or args.unit:
        ok = run_unit_tests()
        all_ok = all_ok and ok
        
    if run_all or args.core or args.benchmarks:
        if not compile_soc_top(waves=args.waves):
            sys.exit(1)
            
    if run_all or args.core:
        ok = run_core_tests(waves=args.waves)
        all_ok = all_ok and ok
        
    if run_all or args.benchmarks:
        ok = run_benchmark_tests(waves=args.waves)
        all_ok = all_ok and ok
        
    total_time = time.time() - t_start
    print(f"{BOLD}========================================================================={RESET}")
    if all_ok:
        print(f"{BOLD}{GREEN}>>> OVERALL REGRESSION STATUS: ALL SUITES PASSED in {total_time:.2f}s <<<{RESET}")
        sys.exit(0)
    else:
        print(f"{BOLD}{RED}>>> OVERALL REGRESSION STATUS: FAILURES DETECTED in {total_time:.2f}s <<<{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
