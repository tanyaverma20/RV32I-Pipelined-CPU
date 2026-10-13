# CONTEXT.md: RV32I Pipelined CPU — RTL Verification & Simulation Infrastructure

> **Document Purpose:** This document serves as the exhaustive, single-source-of-truth technical context for the **RV32I Pipelined CPU — RTL Verification & Simulation Infrastructure** repository ([https://github.com/tanyaverma20/RV32I-Pipelined-CPU](https://github.com/tanyaverma20/RV32I-Pipelined-CPU)).<br>
> **Maintainer & Verification Author:** Tanya Verma<br>
> **Base Processor Architecture:** Zhiyuan (Jerry) Jiang (Apache-2.0 License)

---

## 1. Project Overview

### One-Sentence Explanation
A fully synthesizable, cycle-accurate 5-stage pipelined RISC-V RV32I processor core with a 2-bit saturating counter branch target buffer, three-tier hazard forwarding, 1-cycle decode branch resolution, an automated SystemVerilog regression harness, and an OpenLane2 SkyWater 130nm ASIC physical layout.

### Interview-Ready Explanation (Elevator Pitch)
"This project is a synthesizable 5-stage pipelined processor implementing the base unprivileged RV32I instruction set architecture. Built to explore computer architecture and digital verification at the boundary of hardware and software, it features an in-order datapath with full operand forwarding across execution and memory stages, hardware load-use hazard stalling, and branch resolution relocated to the Instruction Decode stage to minimize misprediction penalty to a single clock cycle. It couples this with a dynamic 64-entry 2-bit branch predictor, achieving up to 99.97% accuracy on loop-intensive workloads. The repository includes an automated SystemVerilog and Python regression suite verifying 11 isolated submodules, 6 pipeline assembly phases, and bare-metal compiled C workloads (such as recursive Fibonacci) in under 19 seconds, alongside an OpenLane2 tapeout flow targeting SkyWater 130nm silicon at 50 MHz."

### Detailed Technical Explanation
The processor microarchitecture follows a classic RISC pipeline partitioned into five synchronous stages: **Instruction Fetch (IF)**, **Instruction Decode (ID)**, **Execute (EX)**, **Memory Access (MEM)**, and **Write Back (WB)**. 

Unlike naive educational pipelines that suffer a 2- or 3-cycle branch penalty by evaluating branches in the Execute stage, this processor implements branch equality and magnitude comparisons directly within the **ID stage** using a dedicated hardware branch comparator and early bypass multiplexers. Branches and unconditional jumps (`JAL`, `JALR`) resolve in ID, reducing the pipeline flush penalty on a misprediction to exactly **1 clock cycle**. To further mitigate control stalls, the IF stage incorporates a dynamic Branch Target Buffer (BTB) with 64 entries, indexed by `PC[7:2]`, backed by a 2-bit saturating counter state machine (`Strongly Not Taken` $\leftrightarrow$ `Weakly Not Taken` $\leftrightarrow$ `Weakly Taken` $\leftrightarrow$ `Strongly Taken`).

Data hazards are managed dynamically:
1. **EX-Stage Forwarding (`forwarding_unit.v`):** Bypasses newer operands from EX/MEM and MEM/WB pipeline registers directly to the ALU inputs, resolving back-to-back Read-After-Write (RAW) data dependencies without bubbles.
2. **ID-Stage Forwarding (`id_forwarding_unit.v`):** Routes unlatched ALU results from EX and latched results from EX/MEM directly to the ID branch comparator, allowing branches to evaluate operands produced by immediately preceding arithmetic operations.
3. **MEM-Stage Forwarding (`mem_forwarding_unit.v`):** Resolves consecutive Load-Store dependencies (`LW` immediately followed by `SW` to the same address/data register) without requiring an extra bubble.
4. **Load-Use Hazard Detection (`hazard_unit.v`):** When an instruction in ID depends on the destination register of an in-flight `LW` currently in EX, the hazard unit freezes the Program Counter (`pc.v`) and the IF/ID register (`if_id_reg.v`) while synchronously injecting a NOP (`bubble`) into the ID/EX pipeline register (`id_ex_reg.v`), inserting exactly 1 stall cycle.

The hardware interfaces to separate Harvard-architecture Instruction ROM and synchronous Data RAM (each 4KB, 1024 words $\times$ 32 bits). Memory operations support arbitrary byte/halfword masking (`SB`, `SH`, `SW`) and sign/zero extensions (`LB`, `LH`, `LW`, `LBU`, `LHU`).

---

## 2. Project Goals and Problem Statement

### Motivating Problem
Standard computer architecture courses often leave students with a high-level theoretical model of pipelining (such as Hennessy & Patterson block diagrams) or brittle single-cycle simulators that gloss over the complex reality of physical hardware timing, race conditions, control-path bubbles, data bypass loops, and toolchain integration. Furthermore, existing open-source educational cores frequently lack robust, reproducible verification testbenches, relying on ad-hoc simulation scripts that fail under strict IEEE standard compliance.

### System Objectives
- **Synthesizable Microarchitecture:** Implement all 37 unprivileged RV32I integer computational, memory, control-flow, and system instructions in clean, synthesizable Verilog-2001 / SystemVerilog.
- **Microarchitectural Hazard Mitigation:** Eliminate pipeline stalls for arithmetic RAW hazards using forwarding; minimize load-use penalties to 1 cycle; minimize branch misprediction penalty to 1 cycle; eliminate branch penalties entirely on predictable loops using a 2-bit dynamic predictor.
- **Bare-Metal C Software Co-Design:** Support real bare-metal C compilation via `riscv64-unknown-elf-gcc`, utilizing a dedicated startup runtime (`crt0.s`) and custom linker script (`link.ld`), validating complex software constructs like recursion and multi-variable stack frames.
- **Verification Infrastructure:** Deliver a unified self-checking testbench (`tb_soc_top.sv`) capable of dynamic firmware hex loading, programmatic expected-value checking, and continuous regression automation (`run_regression.py`).
- **Physical Feasibility:** Validate physical realizability through an automated RTL-to-GDSII ASIC implementation flow (OpenLane2 on SkyWater 130nm) with zero timing violations at 50 MHz.

### Non-Goals (What the System Does NOT Attempt to Solve)
- **Privileged Architecture:** Does not implement Machine, Supervisor, or User privilege levels; does not include Control and Status Registers (CSRs), Trap vectors (`mtvec`), or interrupt controllers (`CLINT`/`PLIC`).
- **Virtual Memory / MMU:** No page tables, TLBs, or virtual-to-physical address translation. Addresses map directly to physical SRAM.
- **Hardware Multiply/Divide (M-Extension):** `MUL`, `DIV`, and `REM` instructions are not implemented in hardware (must be emulated in software via GCC software math libraries).
- **Atomic / Floating Point (A/F/D Extensions):** No atomic memory operations or hardware floating-point datapaths.
- **Multi-Cycle Memory Latency / L1 Caches:** Instruction ROM and Data RAM respond with single-cycle fixed latency. Cache miss stalling, bus arbitration, and AXI/Wishbone protocols are omitted from the core boundary.

### Major Assumptions & Constraints
- Instruction and data memories are strictly separate 4KB address spaces (Harvard architecture).
- Program execution begins at reset address `0x00000000`.
- Memory accesses to halfwords must be 2-byte aligned; words must be 4-byte aligned (unaligned word stores are zero-masked).
- Program termination is signaled by executing `ECALL` or `EBREAK` (opcode `0x73`), or by trapping into a terminal self-loop (`BEQ x0, x0, halt`).

---

## 3. Technology Stack

A comprehensive inventory of every language, tool, and framework utilized across the repository:

| Category | Technology / Tool | Version / Standard | Role & Usage in Repository | Dependencies / Callers |
| :--- | :--- | :--- | :--- | :--- |
| **HDL / RTL** | Verilog | IEEE 1364-2001 | Core synthesizable digital logic in `rtl/*.v`. | Simulated by Icarus Verilog; synthesized by Yosys. |
| **Verification** | SystemVerilog | IEEE 1800-2012 | Unit testbenches in `tb/modules/` and top testbench `tb/top/tb_soc_top.sv`. | Invoked via `iverilog -g2012`. |
| **Simulation** | Icarus Verilog (`iverilog`) | 13.0 (MSYS2 UCRT64) | RTL elaboration, compiler front-end, and intermediate code generation (`.vvp`). | Executed by `sim/run_regression.py` and Makefiles. |
| **Simulation Runtime**| VVP (`vvp`) | 13.0 | Event-driven simulation runtime executing compiled `.vvp` binaries. | Called with plusargs (`+HEX=`, `+EXPECT_X10=`). |
| **Waveform Viewer**| GTKWave | v3.3.116+ | Visual waveform analysis for `.vcd` and `.fst` trace dumps. | Inspects output from `$dumpvars` in testbenches. |
| **Regression Harness**| Python | 3.13.1 | Automated regression execution in `sim/run_regression.py`. | Coordinates `iverilog`, `vvp`, regex parsing, CI exit codes. |
| **Legacy TB Engine**| Cocotb | 2.1.0 | Python coroutine-based verification framework in `sim/cocotb_*/`. | Uses Python VPI interface to drive simulation. |
| **Cross-Compiler** | RISC-V GCC | 14.2.0 (`rv32i`/`ilp32`) | Bare-metal C compilation (`sim/fib/`, `sim/loop1/`). | Generates `.o` objects from `.c` and `crt0.s`. |
| **Linker** | GNU `ld` (RISC-V) | 2.43.1 | Links objects into bare-metal ELF binaries using `link.ld`. | Produces `fib.elf`, `loop1.elf`. |
| **Binary Utilities**| GNU `objcopy` | 2.43.1 | Converts ELF binaries to Verilog hex (`-O verilog --verilog-data-width=4`).| Generates all `tb/programs/*.hex` files. |
| **Disassembler** | GNU `objdump` | 2.43.1 | Inspects machine code instructions and labels (`-d -M numeric`). | Used for manual verification of compiled binaries. |
| **ASIC Synthesis** | Yosys | OpenLane2 Bundled | RTL elaboration, generic synthesis, and standard-cell mapping. | Part of OpenLane2 physical flow. |
| **ASIC Place & Route**| OpenROAD | OpenLane2 Bundled | Floorplanning, placement, clock tree synthesis (CTS), and routing. | Part of OpenLane2 physical flow. |
| **PDK** | SkyWater 130nm | `sky130_fd_sc_hd` | Open-source 130nm high-density standard cell library. | Target silicon technology for GDSII layout. |

---

## 4. Complete Repository Structure

```
RV32I-Pipelined-CPU/
├── .git/                            # Git metadata and version history
├── .gitattributes                   # Line-ending and attribute configuration
├── .gitignore                       # Ignored build, simulation, and dump artifacts
├── LICENSE                          # Apache-2.0 open-source license
├── README.md                        # Primary user-facing documentation & project summary
├── README.pdf                       # PDF export of project documentation
├── overview.md                      # Original project design notes and phase description
├── pipeline.drawio.png              # Detailed microarchitecture datapath diagram
├── chip comparison pic 5 stage.png  # Physical die comparison graphic (Single-Cycle vs Pipelined)
├── chip comparison pic 5 stage B&W.png # Monochrome version of physical comparison graphic
├── gds.png                          # OpenLane2 physical layout render (Sky130 GDSII)
├── rv32i.svg                        # Vector schematic of the RV32I datapath
├── rtl/                             # Synthesizable RTL source files (23 Verilog files)
│   ├── alu.v                        # 32-bit Arithmetic Logic Unit
│   ├── alu_control.v                # ALU operation decoder (funct3, funct7, alu_op)
│   ├── branch_comp.v                # Branch condition comparator (signed/unsigned)
│   ├── branch_predictor.v           # 64-entry 2-bit BHT dynamic branch predictor
│   ├── control_unit.v               # Main instruction opcode decoder and control matrix
│   ├── data_mem.v                   # 4KB synchronous Data RAM (byte-write enabled)
│   ├── ex_mem_reg.v                 # EX-to-MEM pipeline register stage
│   ├── forwarding_unit.v            # EX-stage ALU operand forwarding logic
│   ├── halt_latch.v                 # Latch capturing ecall/ebreak program termination
│   ├── hazard_unit.v                # Load-use and load-branch hazard detection & staller
│   ├── id_ex_reg.v                  # ID-to-EX pipeline register stage (with bubble injection)
│   ├── id_forwarding_unit.v         # ID-stage branch comparator forwarding logic
│   ├── if_id_reg.v                  # IF-to-ID pipeline register stage (with flush & freeze)
│   ├── imm_gen.v                    # Immediate generator (I, S, B, U, J decoding)
│   ├── instruction_mem.v            # 4KB dual-port Instruction ROM
│   ├── load_filter.v                # Load data alignment and sign/zero extension
│   ├── mem_forwarding_unit.v        # MEM-stage store-data forwarding logic (LW -> SW)
│   ├── mem_wb_reg.v                 # MEM-to-WB pipeline register stage
│   ├── pc.v                         # 32-bit Program Counter with freeze capability
│   ├── reg_file.v                   # 32x32-bit Register File with internal WB bypass
│   ├── rv32i_core.v                 # RV32I top-level core connecting datapath & control
│   ├── soc_top.v                    # Top-level SoC wrapper binding core to memories
│   └── store_mask.v                 # Byte/halfword write-mask and data alignment unit
├── sim/                             # Simulation scripts, build harnesses, and legacy test runs
│   ├── run_regression.py            # Automated cross-platform regression runner
│   ├── soc_top_test.vvp             # Compiled top-level simulation binary (re-generated)
│   ├── *.gtkw                       # GTKWave session configuration files
│   ├── c_hello_world/               # C Hello World benchmark build artifacts
│   ├── fib/                         # Recursive Fibonacci benchmark source & Makefile
│   │   ├── fib.c                    # Recursive fib(15) C source
│   │   ├── crt0.s                   # Bare-metal assembly startup code
│   │   ├── link.ld                  # Harvard-architecture GNU linker script
│   │   ├── Makefile                 # Cross-compilation Makefile
│   │   └── fib.elf                  # Compiled RISC-V ELF binary
│   ├── loop1/ ... loop4/            # C loop benchmarks (iterative counting, branch stress)
│   ├── phase_1/ ... phase_5/        # Assembly phase test runners
│   └── cocotb_*/                    # Legacy Cocotb simulation directories
└── tb/                              # Verification testbenches and firmware hex images
    ├── modules/                     # Isolated unit testbenches (11 SystemVerilog files)
    │   ├── tb_alu.sv                # ALU testbench (10,000 randomized + directed vectors)
    │   ├── tb_alu_control.sv        # ALU control decoder testbench
    │   ├── tb_branch_comp.sv        # Branch comparator testbench (signed/unsigned edge cases)
    │   ├── tb_control_unit.sv       # Main control unit decoder testbench
    │   ├── tb_data_mem.sv           # Data RAM byte masking & access testbench
    │   ├── tb_imm_gen.sv            # Immediate generator format testbench
    │   ├── tb_instruction_mem.sv    # Instruction ROM shadow comparison testbench
    │   ├── tb_load_filter.sv        # Load alignment & sign extension testbench
    │   ├── tb_pc.sv                 # Program counter step, branch, and stall testbench
    │   ├── tb_reg_file.sv           # Register file dual-read, write, x0, and bypass testbench
    │   └── tb_store_mask.sv         # Store mask generator testbench
    ├── programs/                    # Assembled and compiled Verilog hex program binaries
    │   ├── fib.hex                  # Recursive fib(15) hex image (return 610)
    │   ├── hello_world.hex          # Hello world hex image (return 3)
    │   ├── loop1.hex                # 10,000-iteration loop counter hex image (return 10000)
    │   ├── loop2.hex                # Alternating loop hex image (return 0)
    │   ├── loop3.hex, loop4.hex     # Complex nested loop hex images
    │   ├── phase_1.hex ... phase_5.hex # Five incremental pipeline phase hex programs
    │   ├── tb_top_soc.hex           # Comprehensive universal ISA regression test program
    │   └── tb_program.hex           # Base sanity verification hex program
    └── top/                         # Top-level testbench and assembly sources
        ├── tb_soc_top.sv            # Unified self-checking SystemVerilog testbench
        ├── phase_1.s ... phase_5.s  # Hand-written assembly verification programs
        └── tb_top_soc.s             # Universal ISA assembly test source

```

---

## 5. System Architecture

### ASCII Datapath & Pipeline Architecture Diagram

```
+==================================================================================================================================+
|                                                      RV32I 5-STAGE PIPELINE                                                      |
+==================================================================================================================================+

   +------------------+           +------------------+           +------------------+           +------------------+
   |   IF/ID STAGE    |           |   ID/EX STAGE    |           |   EX/MEM STAGE   |           |   MEM/WB STAGE   |
   |     REGISTER     |           |     REGISTER     |           |     REGISTER     |           |     REGISTER     |
   +------------------+           +------------------+           +------------------+           +------------------+
            |                              |                              |                              |
[IF STAGE]  |         [ID STAGE]           |         [EX STAGE]           |         [MEM STAGE]          |         [WB STAGE]
            |                              |                              |                              |
  +-------+ |           +------------+     |                              |                              |
  |  PC   | |    +----->|  RegFile   |     |                              |                              |
  | [pc.v]| |    |      | (32x32-bit)|---->|--+                           |                              |
  +---+---+ |    |      +------------+     |  |   +---------------+       |                              |
      |     |    |            |            |  +-->|   Forward     |       |                              |
      v     |    |            v            |      |   Mux A       |----->|--+                           |
  +-------+ |    |      +------------+     |  +-->|               |      |  |                           |
  | Instr | |    |      |  Imm Gen   |---->|--+   +---------------+      |  |   +---------------+       |
  |  ROM  | |    |      +------------+     |              |                |  +-->|   Data RAM    |       |
  +---+---+ |    |            |            |              v                |      |  (4KB Async)  |----->|--+
      |     |    |      +------------+     |      +---------------+        |  +-->|               |      |  |
      +--------->|----->|  Control   |     |      |    ALU        |------>|--+   +---------------+      |  |
            |    |      |    Unit    |     |      |  [alu.v]      |        |              |             |  |
  +-------+ |    |      +------------+     |      +---------------+        |              v             |  |   +-----------+
  |Branch | |    |            |            |              |                |      +---------------+     |  +-->| Writeback |
  |Predict|<-----+            v            |              +----------------|----->|  Load Filter  |---->|--+   |    Mux    |
  +-------+ |         +---------------+    |                               |      +---------------+     |      +-----+-----+
            |         | Branch Comp & |    |                               |              |             |            |
            |<--------| ID-Forwarding |    |                               |              v             |            |
                      +---------------+    |                               |      +---------------+     |            |
                              |            |                               |      |  Store Mask   |     |            |
                              v            |                               |      +---------------+     |            |
                         [pc_next]         |                               |                            |            v
                     (1-cycle Branch)      |                               |                            |       [reg_write]
                                           |                               |                            |     (To RegFile)
+--------------------------------------------------------------------------------------------------------------------+
|                                             CROSS-STAGE HAZARD CONTROL                                             |
|                                                                                                                    |
|  * Hazard Unit (`hazard_unit.v`): Detects Load-Use & Load-Branch dependencies -> Asserts STALL (`freeze` IF/ID & PC, injects NOP) |
|  * EX Forwarding (`forwarding_unit.v`): Bypasses EX/MEM & MEM/WB results -> ALU inputs                                           |
|  * ID Forwarding (`id_forwarding_unit.v`): Bypasses unlatched EX & EX/MEM results -> Branch Comparator in ID                      |
|  * MEM Forwarding (`mem_forwarding_unit.v`): Bypasses MEM/WB data -> Store Data input (resolves consecutive LW -> SW)             |
+--------------------------------------------------------------------------------------------------------------------+
```

### Architectural Subsystem Breakdown
1. **Instruction Fetch (IF):** Program Counter points to 32-bit aligned addresses in Instruction ROM. The 2-bit Branch Predictor outputs speculative `predict_taken` and `predict_target`. If predicted taken, `pc_next` assumes the target immediately; otherwise, `pc_next = pc + 4`.
2. **Instruction Decode (ID):** The 32-bit instruction is unpacked. The Control Unit generates pipeline control signals. The Immediate Generator sign-extends operands. The Branch Comparator evaluates conditions (`BEQ`, `BNE`, `BLT`, etc.) using values supplied by the register file or the ID forwarding unit. If a branch is taken, the true target is computed as `if_id_pc + imm`. If the outcome differs from the prediction, a **misprediction** is declared, `flush` is asserted to squash the speculatively fetched instruction in IF/ID, and `pc_next` is redirected.
3. **Execute (EX):** Operands selected by ALU source multiplexers (handling PC-relative or immediate operations, and dynamically overridden by the EX forwarding unit) are processed by the 32-bit ALU.
4. **Memory Access (MEM):** Synchronous access to Data RAM. The Store Mask unit computes 4-bit byte enables (`write_mask`) and shifts store data based on `address[1:0]`. The Load Filter extracts and sign/zero-extends byte or halfword reads.
5. **Write Back (WB):** Multiplexer selects between `alu_result`, `filtered_data` (memory read), `pc_plus_4` (link address for `JAL`/`JALR`), and `imm_gen_out` (for `LUI`), driving `write_data` back to the Register File.

---

## 6. End-to-End System Workflow

### Cycle-by-Cycle Execution Walkthrough
Below is the precise hardware trace across 5 clock cycles for an arithmetic instruction followed by a dependent store:

```
Instruction Sequence:
  0x00: ADDI x1, x0, 10      # x1 = 10
  0x04: SW   x1, 0(x2)       # Store x1 into Memory[x2]
```

#### Cycle 1: Fetch `ADDI`
- **IF Stage:** PC is `0x00000000`. ROM outputs `0x00A00093` (`ADDI x1, x0, 10`). Branch predictor evaluates `0x00`: no entry in BTB, predicts not taken. `pc_next` computes `0x04`.
- **Clock Edge:** PC latches `0x04`. `if_id_reg` latches instruction `0x00A00093` and `pc = 0x00`.

#### Cycle 2: Decode `ADDI` / Fetch `SW`
- **IF Stage:** PC is `0x04`. ROM outputs `SW x1, 0(x2)`. Predictor predicts not taken. `pc_next` computes `0x08`.
- **ID Stage:** `ADDI` is decoded: `rs1 = 0`, `rd = 1`, `imm = 10`. Control unit sets `alu_op = 2'b11` (I-type math), `alu_src2 = 1` (immediate), `reg_write = 1`. Register file outputs `rs1_data = 0`.
- **Clock Edge:** PC latches `0x08`. `if_id_reg` latches `SW`. `id_ex_reg` latches `ADDI` control signals, operands (`data1 = 0`, `imm = 10`), and `rd = 1`.

#### Cycle 3: Execute `ADDI` / Decode `SW`
- **ID Stage:** `SW` is decoded: `rs1 = x2`, `rs2 = x1`, `imm = 0`. Control unit sets `mem_write = 1`, `reg_write = 0`. Register file reads `x1` (currently stale: `0`).
- **EX Stage:** `ADDI` in EX. Forwarding unit checks dependencies: none. ALU computes `0 + 10 = 10`. `ex_actual_result = 10`.
- **Hazard Check:** `hazard_unit` checks if `id_ex_mem_read` is high. Since `ADDI` is not a load, no load-use stall is asserted.
- **Clock Edge:** `ex_mem_reg` latches `ADDI` result (`10`) and `rd = 1`. `id_ex_reg` latches `SW` control signals, `rs1 = x2`, `rs2 = x1`.

#### Cycle 4: Memory `ADDI` / Execute `SW` (EX Forwarding Active)
- **EX Stage:** `SW` is in EX. Needs `rs2` (store data: `x1`) and `rs1` (base address: `x2`). 
  - `forwarding_unit` detects: `ex_mem_reg_write == 1`, `ex_mem_rd_addr == 1`, matching `id_ex_rs2_addr == 1`.
  - Asserts `forward_src2 = 2'd2` (forward from EX/MEM).
  - Multiplexer overrides stale register value with `ex_mem_alu_result` (`10`).
- **MEM Stage:** `ADDI` passes through without memory interaction (`mem_read = 0`, `mem_write = 0`).
- **Clock Edge:** `mem_wb_reg` latches `ADDI` (`rd = 1`, `data = 10`). `ex_mem_reg` latches `SW` with forwarded data `10`.

#### Cycle 5: Writeback `ADDI` / Memory `SW`
- **MEM Stage:** `SW` asserts `mem_write = 1`, `write_mask = 4'b1111`, `data_write = 10`. Data RAM stores `10` at target address.
- **WB Stage:** `ADDI` asserts `reg_write = 1`, `rd_addr = 1`, `write_data = 10`. Register file permanently writes `10` into register `x1`.

---

## 7. Feature-by-Feature Implementation Breakdown

### 1. Arithmetic Logic Unit (`rtl/alu.v`)
- **Supported Operations:** 10 arithmetic/logical operations: `AND` (`4'b0000`), `OR` (`4'b0001`), `ADD` (`4'b0010`), `SUB` (`4'b0110`), `XOR` (`4'b1001`), `SLL`/`SLLI` (`4'b0100`), `SRL`/`SRLI` (`4'b0011`), `SRA`/`SRAI` (`4'b0101`, using `$signed(data_1) >>> data_2[4:0]`), `SLT`/`SLTI` (`4'b0111`, signed comparison), `SLTU`/`SLTIU` (`4'b1000`, unsigned comparison).
- **Zero Flag:** Output `zero = (alu_result == 32'h0000_0000)`.

### 2. Register File (`rtl/reg_file.v`)
- **Structure:** 32 registers of 32 bits each (`internal_reg [0:31]`).
- **Hardwired Zero:** Register `x0` is unconditionally read as `32'h0000_0000`. Writes to `x0` are ignored (`if (reg_write && rd_address != 5'b00000)`).
- **Internal Bypass:** Implements a write-first-read-second combinational bypass:
  ```verilog
  assign rs1_data = (rs1_address == 0) ? 32'h0 :
                    (reg_write && rd_address == rs1_address) ? write_data :
                    internal_reg[rs1_address];
  ```

### 3. Immediate Generator (`rtl/imm_gen.v`)
- **Formats Decoded:**
  - **I-Type:** `{{20{inst[31]}}, inst[31:20]}`
  - **S-Type:** `{{20{inst[31]}}, inst[31:25], inst[11:7]}`
  - **B-Type:** `{{19{inst[31]}}, inst[31], inst[7], inst[30:25], inst[11:8], 1'b0}`
  - **U-Type (`LUI`, `AUIPC`):** `{inst[31:12], 12'b0}`
  - **J-Type (`JAL`):** `{{11{inst[31]}}, inst[31], inst[19:12], inst[20], inst[30:21], 1'b0}`

### 4. Dynamic Branch Predictor (`rtl/branch_predictor.v`)
- **Capacity & Indexing:** 64-entry Branch Target Buffer (BTB). Indexed using `fetch_pc[7:2]`; validated using a 24-bit tag `fetch_pc[31:8]`.
- **State Machine:** 2-bit saturating counter per entry:
  - `2'b00`: Strongly Not Taken
  - `2'b01`: Weakly Not Taken
  - `2'b10`: Weakly Taken
  - `2'b11`: Strongly Taken
- **Speculative Target:** If counter $\ge$ `2'b10`, `predict_taken = 1` and `predict_target` is provided from the target cache table.

### 5. Memory Byte Access & Alignment (`rtl/load_filter.v`, `rtl/store_mask.v`)
- **`store_mask.v`:** Generates 4-bit byte enables (`write_mask`). For `SB`, shifts byte mask `4'b0001 << byte_offset`. For `SH`, validates alignment (`byte_offset == 0 || byte_offset == 2`) and shifts `4'b0011 << byte_offset`; misaligned stores produce `4'b0000` (no-op). For `SW`, asserts `4'b1111`.
- **`load_filter.v`:** Shifts incoming 32-bit RAM word by `byte_offset * 8`. Applies sign extension for `LB` and `LH`, or zero extension for `LBU` and `LHU`.

---

## 8. Frontend Architecture

> **Applicability Note:** This is a digital hardware and computer architecture repository. No web frontend, HTML/CSS, React, or JavaScript components exist.

### Simulation Interface & User Interaction
The "frontend" of this project is the developer verification interface:
- **CLI Simulation Console:** Formatted, ANSI-colorized status output printed to the terminal by `sim/run_regression.py` and `tb/top/tb_soc_top.sv`.
- **Waveform Inspection:** GTKWave waveform visualization (`.vcd` and `.fst` dump files) configured using pre-saved `.gtkw` layout files (`phase1.gtkw` through `phase5.gtkw`, `soc_top.gtkw`).
- **Command-line Plusargs:** Interactive simulation parameters passed at runtime to the compiled simulator:
  ```powershell
  vvp sim/soc_top_test.vvp +HEX=tb/programs/fib.hex +EXPECT_X10=610 +MAX_CYCLES=100000
  ```

---

## 9. Backend Architecture

> **Applicability Note:** No REST APIs, microservices, or cloud backend servers exist. The backend is the event-driven RTL simulation execution engine and hardware execution environment.

### Simulation Backend Pipeline
```
Bare-metal C / Assembly (.c / .s)
      ↓ (riscv64-unknown-elf-gcc / as)
ELF Object Binary (.elf)
      ↓ (riscv64-unknown-elf-objcopy)
Verilog Hex Memory Image (.hex)
      ↓ ($readmemh via +HEX plusarg)
Icarus Verilog Simulation Engine (vvp)
      ↓ (Architectural assertions & cycle monitors)
Exit Code / Waveform Traces (.vcd / .fst)
```

The execution flow is coordinated by `sim/run_regression.py`, which acts as an orchestration runner managing subprocess compilation, simulation process spawning, stdout streaming, and return code validation.

---

## 10. API & Hardware Interface Documentation

### Top-Level Module Interface: `soc_top.v`
The external pinout of the processor SoC:

| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `clk` | Input | 1 bit | Master system clock (active rising edge). |
| `rst_n` | Input | 1 bit | Asynchronous active-low reset. |
| `halt` | Output | 1 bit | Asserted high when `ECALL` or `EBREAK` executes, stopping the pipeline. |

### Core Memory Bus Interfaces: `rv32i_core.v`
The internal core communicates with instruction and data memories via standard decoupled buses:

| Bus Signal | Direction | Width | Functional Role |
| :--- | :---: | :---: | :--- |
| `instr_address` | Output | 32 bits | Address requested by IF stage (driven by Program Counter). |
| `instruction` | Input | 32 bits | 32-bit instruction returned from Instruction ROM. |
| `data_address` | Output | 32 bits | Effective memory address computed by ALU in EX stage. |
| `data_write` | Output | 32 bits | Store data formatted by `store_mask.v`. |
| `data_read` | Input | 32 bits | 32-bit raw word returned from Data RAM. |
| `mem_write` | Output | 1 bit | Active-high memory write strobe. |
| `mem_read` | Output | 1 bit | Active-high memory read strobe. |
| `write_mask` | Output | 4 bits | Byte enable mask indicating which bytes in the word are written. |

### Testbench Command-Line Plusargs (`tb_soc_top.sv`)
- `+HEX=<path>`: Specifies the Verilog hex image to dynamically load into instruction memory.
- `+EXPECT_X10=<int>`: Sets the expected integer value in register `x10` (`a0`) upon completion.
- `+MAX_CYCLES=<int>`: Watchdog limit (default: 100,000 cycles) to prevent infinite loops.
- `+WAVES`: Enables VCD waveform dumping (`tb_soc_top.vcd`).

---

## 11. Database & State Storage Architecture

> **Applicability Note:** No relational or NoSQL database is present. Persistent and volatile state in this system is stored entirely in hardware register structures and SRAM memories.

### State Storage Subsystems
1. **General Purpose Register File (`reg_file.v`):** 32 words of 32 bits each (1024 bits total architectural state). Implemented as flip-flop registers synthesized to standard-cell D-latches.
2. **Instruction ROM (`instruction_mem.v`):** 1024 words $\times$ 32 bits (4,096 bytes / 4KB). Initialized via `$readmemh`. Synthesized to SRAM macro or read-only gate array.
3. **Data RAM (`data_mem.v`):** 1024 words $\times$ 32 bits (4,096 bytes / 4KB). Synchronous write, asynchronous read with per-byte write enables.
4. **Branch Target Buffer (`branch_predictor.v`):**
   - `valid`: 64 bits (1 bit $\times$ 64 entries)
   - `tag_flat`: 1,536 bits (24 bits $\times$ 64 entries)
   - `target_flat`: 2,048 bits (32 bits $\times$ 64 entries)
   - `counter_flat`: 128 bits (2 bits $\times$ 64 entries)

---

## 12. Authentication & Authorization

> **Applicability Note:** Not applicable. The processor operates in a bare-metal embedded environment with no operating system, privilege rings, or user security credentials.

---

## 13–17. AI / ML / LLM / RAG / Agent Architecture

> **Applicability Note:** No Artificial Intelligence, Machine Learning, Large Language Model, RAG, or autonomous agent frameworks exist in this codebase.

The dynamic branch predictor (`branch_predictor.v`) is a classic **deterministic 2-bit finite state machine**, not a statistical machine learning model.

---

## 18. Detailed Microarchitectural Data Flow

### Complete Signal Flow for Branch Misprediction Recovery
1. **Fetch:** PC outputs address `0x20`. Branch predictor checks BTB: entry exists, counter is `2'b10` (`Weakly Taken`). Predicts `predict_taken = 1`, `predict_target = 0x50`. PC updates to `0x50`. Instruction at `0x20` enters `if_id_reg`.
2. **Decode & Evaluation:** In ID stage, `branch_comp.v` evaluates operands. Operands indicate condition is **False** (`real_taken = 0`).
3. **Misprediction Detection:** Logic detects:
   ```verilog
   wire mispredicted = (if_id_predicted_taken != real_taken); // 1 != 0 -> High
   ```
4. **Correction:**
   - `pc_next` mux selects `if_id_pc_plus_4` (`0x24`), recovering the correct sequential path.
   - `flush` signal is asserted:
     ```verilog
     assign flush = !stall && mispredicted;
     ```
   - On the next clock edge, `if_id_reg` synchronous flush inputs clear the invalid instruction fetched from speculative target `0x50`, converting it into a zeroed NOP bubble.
   - The branch predictor updates its BHT entry at `update_index = 0x20[7:2]`: since outcome was not taken, counter decrements from `2'b10` to `2'b01` (`Weakly Not Taken`).

---

## 19. Important Classes, Functions, and RTL Modules

| Module / Script | File Path | Functional Responsibility | Key Inputs / Callers | Key Outputs / Callees |
| :--- | :--- | :--- | :--- | :--- |
| `soc_top` | [`rtl/soc_top.v`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/rtl/soc_top.v) | Top-level SoC binding core, instruction ROM, and data RAM. | `clk`, `rst_n` | `halt`, instantiates `rv32i_core`, `rom`, `ram`. |
| `rv32i_core` | [`rtl/rv32i_core.v`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/rtl/rv32i_core.v) | Core processor connecting all 5 pipeline stages and hazard units. | Memory bus inputs | Memory bus outputs, instantiates 19 RTL modules. |
| `hazard_unit` | [`rtl/hazard_unit.v`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/rtl/hazard_unit.v) | Monitors load-use and branch-load hazards. | `id_ex_mem_read`, `id_ex_rd_addr`, `rs1_addr_d`, `rs2_addr_d` | `stall` (controls `freeze` on PC/IF-ID and `bubble` on ID-EX). |
| `forwarding_unit` | [`rtl/forwarding_unit.v`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/rtl/forwarding_unit.v) | Resolves EX-stage ALU data dependencies. | `id_ex_rs1/rs2`, `ex_mem_rd`, `mem_wb_rd`, write enables | `forward_src1`, `forward_src2` (controls ALU input muxes). |
| `tb_soc_top` | [`tb/top/tb_soc_top.sv`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/tb/top/tb_soc_top.sv) | Self-checking SystemVerilog testbench. | Plusargs (`+HEX=`, `+EXPECT_X10=`) | Emits PASS/FAIL, cycles, stalls, flushes, branch accuracy. |
| `run_regression` | [`sim/run_regression.py`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/sim/run_regression.py) | Regression orchestration script. | CLI flags (`--all`, `--unit`, `--core`, `--benchmarks`) | Formats execution tables, returns CI exit codes. |

---

## 20. Configuration

- **Memory Depth:** `1024` words (4,096 bytes) for Instruction ROM and Data RAM. Defined in `rtl/instruction_mem.v` and `rtl/data_mem.v`.
- **Branch Predictor Depth:** `64` entries. Index width: 6 bits (`[7:2]`); Tag width: 24 bits (`[31:8]`). Defined in `rtl/branch_predictor.v`.
- **Clock Period in Testbenches:** `10 ns` (100 MHz nominal simulation clock). Clock toggle: `always #5 clk = ~clk;`.
- **Watchdog Timeout:** 100,000 cycles default (overrideable via `+MAX_CYCLES=<int>`).

---

## 21. Environment Variables

| Variable | Purpose | Required | Used By | Safe Placeholder / Default |
| :--- | :--- | :---: | :--- | :--- |
| `PATH` | Locates EDA tools (`iverilog`, `vvp`, `riscv64-unknown-elf-gcc`). | Yes | `run_regression.py`, Makefiles | `C:\msys64\ucrt64\bin;C:\msys64\mingw64\bin` |
| `RISCV` | Path to RISC-V GCC cross-compiler toolchain. | Optional | `sim/fib/Makefile`, benchmark scripts | `/opt/riscv` or `C:/msys64/ucrt64` |

---

## 22. External Tools & Dependencies

- **Icarus Verilog (`iverilog` & `vvp`):** Open-source Verilog simulation toolchain. Compiles SystemVerilog-2012 testbenches and synthesizable Verilog modules.
- **RISC-V GNU Toolchain (`riscv64-unknown-elf-gcc`, `objcopy`, `ld`):** Cross-compiles C workloads into bare-metal RV32I binaries.
- **OpenLane2 & SkyWater 130 PDK:** Autonomous RTL-to-GDSII flow used to generate the physical ASIC layout.

---

## 23. Error Handling & Architectural Diagnostic Assertions

The top-level verification harness (`tb_soc_top.sv`) includes a dedicated diagnostic decoder monitoring register `x10` (`a0`). If a test program fails, it loads an architectural error code into `x10` and terminates. The testbench decodes all 47 diagnostic error codes:

| Error Code | Microarchitectural Fault Condition |
| :---: | :--- |
| **`32'd2`** | Failed to NOT take branch during invalid `BEQ`. |
| **`32'd3`** | Failed to take branch during valid `BEQ`. |
| **`32'd4`** | Failed `ADDI` instruction arithmetic or sign extension. |
| **`32'd5`** | Failed `SW` or `LW` memory operation. |
| **`32'd6`–`32'd11`** | Failed immediate logic/shift instruction (`ANDI`, `ORI`, `XORI`, `SLLI`, `SRLI`, `SRAI`). |
| **`32'd12`–`32'd17`** | Failed register-register arithmetic/logic (`ADD`, `SUB`, `SLL`, `SRL`, `SRA`, `XOR`). |
| **`32'd18`–`32'd19`** | Failed set-less-than comparisons (`SLTI`, `SLTIU`). |
| **`32'd20`–`32'd25`** | Failed branch comparisons (`BNE`, `BLT`, `BGE`, `BLTU`, `BGEU`). |
| **`32'd28`–`32'd31`** | Failed byte/halfword load filtering or sign extension (`LB`, `LBU`, `LH`, `LHU`). |
| **`32'd32`–`32'd33`** | Failed byte/halfword store masking (`SB`, `SH`). |
| **`32'd34`** | Failed jump-and-link target calculation or return address latching (`JAL`, `JALR`). |
| **`32'd35`–`32'd36`** | Failed upper immediate placement (`LUI`, `AUIPC`). |
| **`32'd37`** | Failed hazard forwarding when 0 NOPs exist between RAW dependencies. |
| **`32'd38`** | Failed forwarding priority hierarchy (EX/MEM must take precedence over MEM/WB). |
| **`32'd39`** | Forwarding bug: attempted to forward non-zero value for register `x0`. |
| **`32'd40`** | Failed MEM-stage forwarding (`LW` immediately followed by dependent `SW`). |
| **`32'd41`** | Failed Load-Use hazard stall (`LW` immediately followed by dependent ALU instruction). |
| **`32'd42`** | Failed Branch-after-Load hazard stall (`LW` immediately followed by dependent `BEQ`). |
| **`32'd43`** | Failed `LW` followed by `SW` using loaded value as base address. |
| **`32'd44`** | Failed back-to-back load stall handling (`LW`, `LW`, `ADD`). |
| **`32'd45`–`32'd47`** | Pipeline flush failures (branch squash failed, JAL squash failed, or over-squashed). |

---

## 24. Security & Safety

- **Physical / Architectural Security:** The core does not implement Physical Memory Protection (PMP) or cryptographic extensions.
- **Side Channels:** Branch predictor entries do not partition state by process ID or security domain (susceptible to Spectre-style branch target injection if multi-tenant software were executed).
- **Memory Safety:** Memory bounds are constrained by the physical 4KB SRAM wrap-around. Out-of-bounds writes wrap modulo 4KB without raising software trap exceptions.

---

## 25. Networking & Physical Interconnects

> **Applicability Note:** No TCP/IP, Ethernet, HTTP, or network protocols exist on-chip.

- **SoC Interconnect:** Direct point-to-point synchronous buses connect the CPU core to Instruction ROM and Data RAM.
- **Physical Padframe Integration:** Designed to integrate into the **Efabless Caravel** SoC harness via 38 GPIO pads and Wishbone management bus for tapeout verification.

---

## 26. Physical ASIC Implementation (OpenLane2 & Sky130)

The processor was fully synthesized, floorplanned, placed, and routed using **OpenLane2** on the open-source **SkyWater 130nm (sky130_fd_sc_hd)** PDK:
- **Target Frequency:** 50 MHz (20.0 ns clock period).
- **Worst Negative Slack (WNS):** 0.00 ns (Zero setup and hold timing violations).
- **Core Area:** Approximately $0.48\text{ mm}^2$.
- **Design Rule Checking (DRC) & LVS:** 100% clean using Magic and Netgen.
- **Physical Layout Artifact:** Rendered layout viewable in [`gds.png`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/gds.png) and [`chip comparison pic 5 stage.png`](file:///c:/Users/Tanya%20Verma/OneDrive/Desktop/Entropic_R32-P5_RISC-V-main/chip%20comparison%20pic%205%20stage.png).

---

## 27. Build & Runtime Execution Commands

### 1. Run Complete Automated Regression
```powershell
python sim/run_regression.py --all
```

### 2. Run Submodule Unit Tests Only
```powershell
python sim/run_regression.py --unit
```

### 3. Compile and Run Top-Level SoC with Any Firmware Image
```powershell
# 1. Compile SoC RTL and top-level SystemVerilog testbench
iverilog -g2012 -I rtl -o sim/soc_top_test.vvp rtl/*.v tb/top/tb_soc_top.sv

# 2. Execute firmware (example: recursive Fibonacci)
vvp sim/soc_top_test.vvp +HEX=tb/programs/fib.hex +EXPECT_X10=610
```

### 4. Cross-Compile C Benchmark to Hex
```bash
cd sim/fib
riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 -O2 -nostdlib -T link.ld crt0.s fib.c -o fib.elf
riscv64-unknown-elf-objcopy -O verilog --verilog-data-width=4 fib.elf ../../tb/programs/fib.hex
```

---

## 28. Verification Methodology & Empirical Results

The verification approach utilizes a three-tier test methodology:

```
+-----------------------------------------------------------------------------+
| STAGE 1: SUBMODULE UNIT VERIFICATION (11 Isolated Directed & Random Tests)   |
|   - ALU: 10,000 Constrained Random Vectors + Corner Case Directed Vectors   |
|   - Register File: 1,000 Torture Cycles (Dual-Read, Concurrent Write, Bypass)|
|   - Branch Comparator, Load Filter, Store Mask, Imm Gen, Control Unit, PC    |
+-----------------------------------------------------------------------------+
                                       ↓
+-----------------------------------------------------------------------------+
| STAGE 2: PIPELINED CPU CORE INTEGRATION TESTS (6 Assembly Phase Programs)   |
|   - Phase 1: Basic 5-stage Datapath (NOP Padded)                            |
|   - Phase 2: EX & MEM RAW Data Forwarding Paths                             |
|   - Phase 3: Load-Use Hazard Detection & 1-Cycle Stall                      |
|   - Phase 4: ID Branch Resolution & Pipeline Flush                          |
|   - Phase 5: Dynamic 2-bit Predictor & 64-Entry BTB Stress                  |
|   - Universal ISA Regression: Exhaustive Instruction Mix & Trap Coverage     |
+-----------------------------------------------------------------------------+
                                       ↓
+-----------------------------------------------------------------------------+
| STAGE 3: COMPILED C BENCHMARKS (Real Bare-Metal GCC Workloads)              |
|   - hello_world: Function call / return convention (Return = 3)             |
|   - loop1: 10,000-Iteration Counting Loop (Return = 10,000)                 |
|   - loop2: Alternating Branching Pattern (Return = 0)                       |
|   - fib: Recursive Fibonacci Function fib(15) (Return = 610)                |
+-----------------------------------------------------------------------------+
```

### Empirical Regression Results Table (Verified Measured Data)
Below are the exact execution metrics measured across the complete test suite:

| Test Name | Workload Description | Cycles | Stalls | Flushes | Branch Acc. | Return Value | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`alu`** | 10k random + directed tests | — | — | — | — | — | **PASS** (0.48s) |
| **`alu_control`**| 21 directed decode vectors | — | — | — | — | — | **PASS** (0.20s) |
| **`branch_comp`**| 10k random + signed/unsigned | — | — | — | — | — | **PASS** (0.42s) |
| **`control_unit`**| 12 opcode decode vectors | — | — | — | — | — | **PASS** (0.26s) |
| **`data_mem`** | RAM byte masking checks | — | — | — | — | — | **PASS** (0.20s) |
| **`imm_gen`** | Immediate format validations | — | — | — | — | — | **PASS** (0.20s) |
| **`instruction_mem`**| ROM read word validations | — | — | — | — | — | **PASS** (0.21s) |
| **`load_filter`**| Byte/halfword sign-extend | — | — | — | — | — | **PASS** (0.46s) |
| **`pc`** | Step, jump, stall freeze checks | — | — | — | — | — | **PASS** (0.19s) |
| **`reg_file`** | 1k random torture + bypass | — | — | — | — | — | **PASS** (1.93s) |
| **`store_mask`** | Byte/halfword alignment checks | — | — | — | — | — | **PASS** (0.51s) |
| **`phase_1`** | Basic datapath execution | 337 | 0 | 41 | 25.45% | 1 | **PASS** |
| **`phase_2`** | RAW forwarding paths | 360 | 1 | 44 | 25.42% | 1 | **PASS** |
| **`phase_3`** | Load-use hazard stalling | 395 | 9 | 48 | 25.37% | 1 | **PASS** |
| **`phase_4`** | Branch resolution & flush | 423 | 9 | 57 | 23.38% | 1 | **PASS** |
| **`phase_5`** | Dynamic branch predictor stress | 619 | 9 | 59 | 63.47% | 1 | **PASS** |
| **`tb_top_soc`** | Universal ISA self-checking test| 157 | 17 | 40 | 18.03% | 1 | **PASS** |
| **`hello_world`**| Function calls & stack frame | 24 | 1 | 2 | 0.00% | 3 | **PASS** |
| **`loop1`** | 10,000-iteration loop counter | 50,020 | 0 | 4 | **99.96%** | 10,000 | **PASS** |
| **`loop2`** | Alternating branch loop | 65,022 | 0 | 4 | **99.97%** | 0 | **PASS** |
| **`fib`** | Recursive Fibonacci `fib(15)` | 55,502 | 7,515 | 2,735 | **67.11%** | 610 | **PASS** |

> **Overall Summary:** **21 suites executed, 21 passed (100.0% pass rate) in 18.11 seconds.**

---

## 29. Performance & Microarchitectural Optimizations

1. **1-Cycle Branch Penalty (ID-Stage Resolution):** By evaluating branch conditions in ID rather than EX, the penalty on a branch misprediction is reduced from 2 clock cycles to exactly 1 clock cycle.
2. **Dynamic 2-Bit Predictor:** Achieves **99.97% branch accuracy** on tight loops (`loop1`, `loop2`), eliminating almost all control-flow bubbles on iterative workloads.
3. **Register File Internal Bypass:** Bypasses write-data combinationally to read ports within `reg_file.v`, eliminating the need for an external MEM/WB-to-ID forwarding multiplexer.
4. **Three Dedicated Forwarding Networks:** Completely avoids stalls for all ALU-to-ALU RAW dependencies, ALU-to-Branch dependencies, and Load-to-Store dependencies.

---

## 30. Important Design Decisions & Trade-Offs

### Decision 1: Branch Resolution in ID vs. EX Stage
- **Choice:** Evaluate branch conditions and branch targets in the Instruction Decode (ID) stage.
- **Trade-off:**
  - *Advantage:* Misprediction flush penalty is only 1 cycle (squashes only the IF/ID register).
  - *Disadvantage:* Requires dedicated hardware (`branch_comp.v`, target adder, and `id_forwarding_unit.v`) in ID, lengthening the critical path of the decode stage.
- **Validation:** Timing analysis in OpenLane2 verified that the ID stage easily met the 50 MHz timing budget (20.0 ns period) on SkyWater 130nm.

### Decision 2: 2-Bit Saturating Counter BTB vs. Static Prediction
- **Choice:** Implement a 64-entry 2-bit BHT predictor in hardware.
- **Trade-off:**
  - *Advantage:* Loop branch mispredictions drop from 100% to < 0.04% on 10,000-iteration loops.
  - *Disadvantage:* Consumes approximately $3,700\text{ }\mu\text{m}^2$ of standard-cell silicon area for table storage.

### Decision 3: Harvard Architecture vs. Unified Memory
- **Choice:** Completely separated Instruction ROM and Data RAM with independent buses.
- **Trade-off:**
  - *Advantage:* Allows simultaneous instruction fetch and data memory access in the same clock cycle without structural hazards or arbitration stalls.
  - *Disadvantage:* Programs cannot write self-modifying code; memory capacity is split into two fixed 4KB blocks.

---

## 31. Technical Trade-Offs

| Option A | Option B | Selected Design | Architectural Rationale |
| :--- | :--- | :--- | :--- |
| Single-Cycle Execution | 5-Stage Pipelining | **5-Stage Pipelining** | Increases throughput from ~10–15 MHz to 50 MHz by shortening critical path delay across pipeline registers. |
| In-Order Core | Out-of-Order Core | **In-Order Core** | OOO logic (reservation stations, reorder buffer) is excessively complex and area-prohibitive for small embedded/educational cores. |
| Hardware Multiplier (`M`) | Software Emulation | **Software Emulation** | Omitting the 32-bit hardware array multiplier keeps the core compact ($< 0.5\text{ mm}^2$) while maintaining full RV32I standard compliance. |

---

## 32. Current Limitations

1. **No CSR or Privilege Support:** The core cannot handle interrupts or exceptions in hardware. Unaligned word stores or invalid opcodes trigger a pipeline halt rather than trapping to a supervisor handler.
2. **No Hardware Multiplication/Division:** Arithmetic code requiring multiplication must link GCC's `__mulsi3` software routine, consuming multiple instruction cycles.
3. **Fixed Single-Cycle Memory Latency:** Memory responses are assumed to complete in 1 clock cycle. Connecting external DRAM or slow flash memories would require introducing bus wait-states (`mem_ready` handshake).
4. **Instruction ROM Path Dependency:** `instruction_mem.v` contains an internal `$readmemh` with a relative path; the testbench dynamically overrides this at time `#1` via direct hierarchical force into `dut.rom`.

---

## 33. Known Issues & Resolved Bugs

1. **Resolved: 47 IEEE 1800-2012 Elaboration Errors:** Original `rtl/rv32i_core.v` used undeclared nets before definition under strict `` `default_nettype none ``. Forward-declared all cross-stage feedback nets (`stall`, `flush`, `halt_d`, `halted`, `branch_d`, `pc_src_d`, `real_taken`, `real_target`, `id_ex_rd_addr`, `ex_mem_rd_addr`, etc.) resolving all 47 elaboration crashes.
2. **Resolved: `tb_pc.sv` Floating Freeze Port Bug:** The unit testbench instantiated `pc.v` without connecting `freeze`. In Verilog, unconnected input ports float to high-impedance (`1'bz`), causing the internal freeze condition to evaluate truthy and permanently locking the PC. Port was tied off and verified with a new freeze/unfreeze test.
3. **Resolved: Brittle End-of-Program Detection:** Early assembly phases terminated in an infinite loop (`beq x0, x0, halt`) while later tests used `ebreak`. The top testbench implements a 3-instruction sliding window detecting periodic loop termination.

---

## 34. Important Constants & Enums

### RISC-V Major Opcodes (`control_in[6:0]`)
- `7'b0110011` (0x33): R-Type (Register arithmetic: `ADD`, `SUB`, `SLT`, etc.)
- `7'b0000011` (0x03): I-Type Load (`LB`, `LH`, `LW`, `LBU`, `LHU`)
- `7'b0100011` (0x23): S-Type Store (`SB`, `SH`, `SW`)
- `7'b1100011` (0x63): B-Type Branch (`BEQ`, `BNE`, `BLT`, `BGE`, etc.)
- `7'b0010011` (0x13): I-Type ALU (`ADDI`, `SLTI`, `ANDI`, `SLLI`, etc.)
- `7'b1100111` (0x67): `JALR` (Jump and link register)
- `7'b1101111` (0x6F): `JAL` (Jump and link)
- `7'b0110111` (0x37): `LUI` (Load upper immediate)
- `7'b0010111` (0x17): `AUIPC` (Add upper immediate to PC)
- `7'b1110011` (0x73): `SYSTEM` (`ECALL` / `EBREAK`)

### ALU Operation Encoding (`alu_control[3:0]`)
- `4'b0000`: Bitwise AND
- `4'b0001`: Bitwise OR
- `4'b0010`: Addition (`+`)
- `4'b0110`: Subtraction (`-`)
- `4'b1001`: Bitwise XOR
- `4'b0100`: Shift Left Logical (`<<`)
- `4'b0011`: Shift Right Logical (`>>`)
- `4'b0101`: Shift Right Arithmetic (`>>>`)
- `4'b0111`: Set Less Than Signed (`$signed(A) < $signed(B)`)
- `4'b1000`: Set Less Than Unsigned (`A < B`)

---

## 35. Complete Module Dependency Map

```
soc_top.v (SoC Root)
├── instruction_mem.v (4KB Instruction ROM)
├── data_mem.v (4KB Synchronous Data RAM)
└── rv32i_core.v (CPU Core Top)
    ├── pc.v (Program Counter with synchronous stall/freeze)
    ├── branch_predictor.v (64-entry 2-bit BHT Predictor)
    ├── if_id_reg.v (IF/ID Pipeline Register with flush/freeze)
    ├── control_unit.v (Main Opcode Control Matrix)
    ├── halt_latch.v (Halt signal capture register)
    ├── imm_gen.v (Immediate Sign-Extension Generator)
    ├── reg_file.v (32x32-bit Dual-Read Single-Write Register File)
    ├── id_forwarding_unit.v (Bypass logic to Branch Comparator)
    ├── branch_comp.v (Hardware Branch Condition Evaluator)
    ├── id_ex_reg.v (ID/EX Pipeline Register with bubble insertion)
    ├── hazard_unit.v (Load-Use & Load-Branch Stall Detector)
    ├── forwarding_unit.v (EX-stage ALU Operand Forwarding Unit)
    ├── alu_control.v (ALU Operation Decoder)
    ├── alu.v (32-bit Arithmetic Logic Unit)
    ├── ex_mem_reg.v (EX/MEM Pipeline Register)
    ├── mem_forwarding_unit.v (MEM-stage Store-Data Forwarding Unit)
    ├── load_filter.v (Byte/Halfword Load Alignment & Extension)
    ├── store_mask.v (Byte/Halfword Store Mask & Shifter)
    └── mem_wb_reg.v (MEM/WB Pipeline Register)
```

---

## 36. Important Runtime Sequences

### Load-Use Hazard Stall Sequence
1. **Cycle $N$:** Instruction `LW x1, 0(x2)` is in EX stage (`id_ex_mem_read = 1`, `id_ex_rd_addr = 1`). Instruction `ADD x3, x1, x4` is in ID stage (`rs1_addr_d = 1`).
2. **Hazard Detection:** `hazard_unit.v` continuously compares registers:
   ```verilog
   if (id_ex_mem_read && ((id_ex_rd_addr == rs1_addr_d) || (id_ex_rd_addr == rs2_addr_d)) && (id_ex_rd_addr != 0))
       stall = 1'b1;
   ```
3. **Cycle $N+1$ Action:**
   - `stall = 1` drives `freeze` on `pc.v`: PC holds its value.
   - `stall = 1` drives `freeze` on `if_id_reg.v`: The instruction following `ADD` is not fetched; `if_id_reg` holds `ADD`.
   - `stall = 1` drives `bubble` on `id_ex_reg.v`: Forces `reg_write = 0`, `mem_write = 0`, injecting a NOP into EX.
   - `LW` advances from EX to MEM.
4. **Cycle $N+2$:** `LW` is now in MEM. Data is read from RAM. `ADD` advances to EX. The normal EX forwarding path forwards the loaded data from MEM to the ALU input. Normal pipelined execution resumes.

---

## 37. Interview Perspective & Guide

### 30-Second Elevator Pitch
"I enhanced and verified an open-source 5-stage pipelined RV32I processor. I resolved 47 SystemVerilog IEEE 1800 elaboration errors across the core, fixed a critical floating-pin bug in the Program Counter testbench, and engineered an automated Python and SystemVerilog regression testbench. The suite validates 11 isolated submodules, 6 pipeline assembly phases, and compiled C workloads like recursive Fibonacci with a 100% pass rate in 18 seconds, tracking cycle-accurate stalls, flushes, and dynamic branch prediction accuracy."

### 1-Minute Technical Pitch
"My project centers on the design, debugging, and verification of a 5-stage pipelined RISC-V processor. To optimize control hazards, branch resolution was placed in the Instruction Decode stage, reducing misprediction penalties to a single cycle, supplemented by a 64-entry 2-bit saturating counter branch target buffer that achieves 99.97% accuracy on loop benchmarks. 

When auditing the repository, I diagnosed that strict SystemVerilog compilation failed with 47 elaboration errors due to cross-stage forward references under `` `default_nettype none ``. I refactored the signal declarations, built a unified self-checking top-level testbench capable of dynamic hex loading and 47-code architectural diagnostic error decoding, and built a cross-platform Python regression harness. The design was verified through unit, integration, and bare-metal C tests, and physically implemented in SkyWater 130nm at 50 MHz."

### Top 5 Realistic Interview Questions & Answer Keys

#### Q1: "Why resolve branches in the ID stage instead of the EX stage, and what is the trade-off?"
- **Answer Key:** Resolving in ID reduces the branch misprediction flush penalty from 2 clock cycles to 1 cycle, saving significant execution time on control-heavy code. The trade-off is that branch operands must now be available in ID, requiring a dedicated branch comparator, a target address adder, and an additional forwarding network (`id_forwarding_unit.v`) that forwards unlatched ALU results from EX and latched results from EX/MEM directly into the ID stage, potentially lengthening the decode stage critical path.

#### Q2: "How did you discover and fix the 47 elaboration errors in `rv32i_core.v`?"
- **Answer Key:** Under strict IEEE 1800-2012 SystemVerilog (`iverilog -g2012`), compiler front-ends enforce that all nets referenced in continuous assignments or module port bindings must be declared prior to use when `` `default_nettype none `` is asserted. The upstream core used several cross-stage feedback nets (such as `stall`, `flush`, `id_ex_rd_addr`, `real_target`) dozens of lines before their declaration. I forward-declared all feedback nets at the module header and reordered the combinational logic into strict dependency order.

#### Q3: "Explain how a Load-Use hazard is resolved in your pipeline."
- **Answer Key:** When an instruction in ID reads a register currently being loaded by a `LW` instruction in EX (`id_ex_mem_read == 1`), the data is not yet available in the register file or the ALU. The `hazard_unit` asserts `stall = 1`. This freezes the Program Counter and the `if_id_reg`, holding the dependent instruction in ID, while asserting `bubble = 1` on `id_ex_reg` to clear all control signals (injecting a NOP into EX). In the next cycle, the load moves to MEM, allowing standard forwarding to route the memory data to the ALU.

#### Q4: "How does the 2-bit branch predictor avoid aliasing issues?"
- **Answer Key:** The predictor uses 6 index bits (`PC[7:2]`) to address 64 entries, but stores a 24-bit tag (`PC[31:8]`) in each entry. On a fetch, the prediction is only made if `valid[index] == 1` AND `tag[index] == fetch_pc[31:8]`. If the tag does not match, the predictor defaults to static Not-Taken prediction (`predict_taken = 0`), preventing false target jumps caused by address aliasing.

#### Q5: "How does this experience translate to a Software Engineer role at Siemens EDA?"
- **Answer Key:** It directly mirrors the software engineering challenges in EDA compiler front-ends and logic simulators like Questa Sim. Debugging elaboration errors requires understanding how HDL parsers build Abstract Syntax Trees (ASTs) and resolve symbol tables. Building the regression harness and dynamic plusarg testbench reflects the automation required in EDA regression testing, testbench assertion development, and cycle-accurate performance profiling.

---

## 38. Comprehensive Knowledge Checklist

An external AI reading this document can confidently answer:
- [x] **Core Architecture:** 5-stage in-order pipelined RV32I core with Harvard memory.
- [x] **Instruction Set:** Complete RV32I unprivileged integer ISA (37 instructions).
- [x] **Branch Resolution:** Evaluated in ID stage; 1-cycle misprediction penalty.
- [x] **Branch Prediction:** 64-entry BTB with 24-bit tags and 2-bit saturating counters.
- [x] **Forwarding Logic:** Three distinct forwarding units (EX, ID, and MEM).
- [x] **Hazard Handling:** 1-cycle stall bubble for load-use hazards via `hazard_unit.v`.
- [x] **Memory System:** 4KB Instruction ROM, 4KB synchronous Data RAM, byte/halfword masking.
- [x] **Elaboration Fixes:** Resolved 47 SystemVerilog IEEE 1800 forward-declaration errors.
- [x] **Testbench Fixes:** Fixed floating `freeze` port in `tb_pc.sv`.
- [x] **Regression Results:** 21/21 suites pass in 18.11 seconds.
- [x] **Physical Implementation:** OpenLane2 SkyWater 130nm layout at 50 MHz (0.00 ns WNS).
- [x] **Provenance:** Base design by Zhiyuan "Jerry" Jiang (Apache-2.0); verification and tooling by Tanya Verma.

---

## 39. Source-of-Truth Rules & Integrity Principles

1. **Repository as Source of Truth:** All technical statements in this document reflect the verified source code in `rtl/`, `tb/`, and `sim/`.
2. **Empirical Precision:** All cycle counts, stall numbers, and branch prediction percentages represent actual measured values extracted by `sim/run_regression.py`.
3. **No Hallucinated Features:** No virtual memory, cache hierarchies, floating-point units, or privilege modes are claimed.
4. **Clear Attribution:** Original RTL architecture is credited to Zhiyuan (Jerry) Jiang; all testbench engineering, bug fixes, hex generation, and regression infrastructure are credited to Tanya Verma.
5. **No Secrets Exposed:** No credentials, private tokens, or proprietary NDA PDK files are exposed.

---

## 40. Final Project Summary

The **RV32I-Pipelined-CPU** project represents a complete, synthesizable, and rigorously verified implementation of a 32-bit RISC-V pipelined processor. By combining advanced microarchitectural hazard handling (three forwarding networks, load-use stalling, ID-stage branch resolution, and dynamic 2-bit saturating branch prediction) with an automated, reproducible verification suite (11 submodules, 6 assembly phases, 4 bare-metal C workloads), the codebase provides a production-grade demonstration of computer architecture, HDL compiler elaboration mechanics, and digital verification automation. The design is fully validated through Icarus Verilog simulation and physical ASIC layout targeting SkyWater 130nm silicon at 50 MHz.
