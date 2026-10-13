/*
 * RV32I Pipelined CPU — RTL Verification & Simulation Infrastructure
 * Top-Level Self-Checking SystemVerilog Testbench
 *
 * Maintainer & Verification Author: Tanya Verma (https://github.com/tanyaverma20/RV32I-Pipelined-CPU)
 * Base Processor Architecture: Zhiyuan (Jerry) Jiang (Apache-2.0)
 *
 * Provides a unified, standalone, reproducible verification environment
 * capable of running all test phases (phase 1 - 5), universal test (tb_top_soc),
 * and compiled C benchmarks with zero external Python/cocotb requirements.
 *
 * Usage:
 *   iverilog -g2012 -o sim/soc_sim tb/top/tb_soc_top.sv rtl/soc_top.v rtl/...
 *   vvp sim/soc_sim +HEX=tb/programs/phase_5.hex
 *   vvp sim/soc_sim +HEX=tb/programs/tb_top_soc.hex
 */

`default_nettype none
`timescale 1ns/1ps

module tb_soc_top;
  logic clk;
  logic rst_n;
  wire halt;

  // DUT instantiation
  soc_top dut (
    .clk(clk),
    .rst_n(rst_n),
    .halt(halt)
  );

  // Clock generation: 10ns period (100 MHz clock)
  initial clk = 0;
  always #5 clk = ~clk;

  string hex_file = "";
  integer max_cycles = 200000;
  integer expected_x10 = 1;
  logic expect_x10_set = 0;
  integer cycle_count = 0;
  integer branch_eval_count = 0;
  integer branch_mispredict_count = 0;
  integer stall_count = 0;
  integer flush_count = 0;

  // PC history tracking for Phase 1-4 legacy self-loops (beq x0, x0, halt)
  logic [31:0] pc_history [0:5];
  integer pc_repeat_count = 0;
  logic program_finished = 0;

  // Signal aliases for monitoring and metrics
  wire [31:0] pc = dut.cpu.pc_out;
  wire [31:0] x10 = dut.cpu.cpu_reg_file.internal_reg[10];
  wire stall = dut.cpu.stall;
  wire flush = dut.cpu.flush;
  wire mispredicted = dut.cpu.mispredicted;
  wire branch_update = dut.cpu.cpu_branch_predictor.update_en;

  initial begin
    // Check waveform dump request
    if ($test$plusargs("WAVES")) begin
      $dumpfile("sim/soc_top.vcd");
      $dumpvars(0, tb_soc_top);
    end

    // Allow dynamic expected return code override (e.g. for C benchmarks)
    if ($value$plusargs("EXPECT_X10=%d", expected_x10)) begin
      expect_x10_set = 1;
      $display("[TB] Expected return value x10 set to: %0d", expected_x10);
    end

    // Allow dynamic HEX override
    #1; // Wait 1 delta time unit so rom.v initial $readmemh finishes first
    if ($value$plusargs("HEX=%s", hex_file)) begin
      $display("------------------------------------------------------------------------------------------");
      $display("[TB] Loading program HEX into ROM from: %s", hex_file);
      $readmemh(hex_file, dut.rom.rom);
      $display("------------------------------------------------------------------------------------------");
    end else begin
      $display("[TB] Using default instruction ROM contents");
    end

    // Pre-initialize RAM array as required by regression programs
    dut.ram.mem_array[0] = 32'd1; // Address 0
    dut.ram.mem_array[1] = 32'd2; // Address 4
    dut.ram.mem_array[2] = 32'd3; // Address 8

    // Reset sequence: 5 cycles
    rst_n = 1'b0;
    repeat (5) @(posedge clk);
    rst_n = 1'b1;
    $display("[TB] CPU reset deasserted. Simulation started...");

    // Run until halt, terminal loop, or timeout
    while (cycle_count < max_cycles && !halt && !program_finished) begin
      @(posedge clk);
      cycle_count++;

      if (stall) stall_count++;
      if (flush) flush_count++;
      if (branch_update) begin
        branch_eval_count++;
        if (mispredicted) branch_mispredict_count++;
      end

      pc_history[5] = pc_history[4];
      pc_history[4] = pc_history[3];
      pc_history[3] = pc_history[2];
      pc_history[2] = pc_history[1];
      pc_history[1] = pc_history[0];
      pc_history[0] = pc;

      // Terminal loop detection: 3-instruction loop period repeating 6 times
      if (cycle_count > 20 &&
          pc_history[0] == pc_history[3] &&
          pc_history[1] == pc_history[4] &&
          pc_history[2] == pc_history[5]) begin
        pc_repeat_count++;
        if (pc_repeat_count >= 6) program_finished = 1;
      end else begin
        pc_repeat_count = 0;
      end
    end

    #1; // Settle combinational logic

    $display("==========================================================================================");
    $display("                             SIMULATION EXECUTION REPORT                                  ");
    $display("==========================================================================================");
    $display("  Total Elapsed Cycles   : %0d", cycle_count);
    $display("  Stall Cycles Inserted  : %0d", stall_count);
    $display("  Flush Cycles Triggered : %0d", flush_count);
    if (branch_eval_count > 0) begin
      real accuracy;
      accuracy = 100.0 * (branch_eval_count - branch_mispredict_count) / branch_eval_count;
      $display("  Branches Resolved      : %0d", branch_eval_count);
      $display("  Mispredictions         : %0d", branch_mispredict_count);
      $display("  Branch Predict Accuracy: %0.2f%%", accuracy);
    end
    $display("  CPU Halt Signal        : %b (Terminal Loop Detected: %b)", halt, program_finished);
    $display("  Program Counter at Stop: 0x%08h", pc);
    $display("  Return Code Register x10: %0d (0x%08h)", x10, x10);
    $display("==========================================================================================");

    if ((halt || program_finished) && x10 == expected_x10) begin
      $display("\033[32m[PASS] CPU completed successfully with Return Code x10 = %0d (ALL CHECKS PASSED)\033[0m", x10);
      $display("==========================================================================================");
      $finish(0);
    end else if (halt || program_finished) begin
      $display("\033[31m[FAIL] CPU completed with code x10 = %0d (Expected: %0d)\033[0m", x10, expected_x10);
      if (!expect_x10_set) print_error_description(x10);
      $display("==========================================================================================");
      $fatal(1, "Verification failed with return code: %0d", x10);
    end else begin
      $display("\033[31m[TIMEOUT] Simulation exceeded %0d cycles without terminating.\033[0m", max_cycles);
      $display("==========================================================================================");
      $fatal(2, "Simulation timed out after %0d cycles", max_cycles);
    end
  end

  task print_error_description(input [31:0] code);
    case (code)
      32'd2:  $display("  Detail: Failed to NOT take branch during invalid beq");
      32'd3:  $display("  Detail: Failed to take branch during valid beq");
      32'd4:  $display("  Detail: Failed addi instruction");
      32'd5:  $display("  Detail: Failed sw or lw memory operation");
      32'd6:  $display("  Detail: Failed andi instruction");
      32'd7:  $display("  Detail: Failed ori instruction");
      32'd8:  $display("  Detail: Failed xori instruction");
      32'd9:  $display("  Detail: Failed slli instruction");
      32'd10: $display("  Detail: Failed srli instruction");
      32'd11: $display("  Detail: Failed srai instruction");
      32'd12: $display("  Detail: Failed add instruction");
      32'd13: $display("  Detail: Failed sub instruction");
      32'd14: $display("  Detail: Failed sll instruction");
      32'd15: $display("  Detail: Failed srl instruction");
      32'd16: $display("  Detail: Failed sra instruction");
      32'd17: $display("  Detail: Failed xor instruction");
      32'd18: $display("  Detail: Failed slti instruction (signed immediate comparison)");
      32'd19: $display("  Detail: Failed sltiu instruction (unsigned immediate comparison)");
      32'd20: $display("  Detail: Failed to take branch during valid bne");
      32'd21: $display("  Detail: Failed to NOT take branch during invalid bne");
      32'd22: $display("  Detail: Failed to take branch during valid blt (signed)");
      32'd23: $display("  Detail: Failed to NOT take branch during invalid bltu (unsigned)");
      32'd24: $display("  Detail: Failed to NOT take branch during invalid bge (signed)");
      32'd25: $display("  Detail: Failed to take branch during valid bgeu (unsigned)");
      32'd26: $display("  Detail: Failed and instruction");
      32'd27: $display("  Detail: Failed or instruction");
      32'd28: $display("  Detail: Failed lb instruction (sign extension incorrect)");
      32'd29: $display("  Detail: Failed lbu instruction (zero extension incorrect)");
      32'd30: $display("  Detail: Failed lh instruction (sign extension incorrect)");
      32'd31: $display("  Detail: Failed lhu instruction (zero extension incorrect)");
      32'd32: $display("  Detail: Failed sb instruction (neighboring byte corrupted or write failed)");
      32'd33: $display("  Detail: Failed sh instruction (neighboring halfword corrupted or write failed)");
      32'd34: $display("  Detail: Failed jal/jalr instruction (link address or jump target incorrect)");
      32'd35: $display("  Detail: Failed lui instruction (upper immediate placement incorrect)");
      32'd36: $display("  Detail: Failed auipc instruction (PC-relative upper immediate incorrect)");
      32'd37: $display("  Detail: Failed forwarding when 0 NOP between RAW dependency");
      32'd38: $display("  Detail: Failed forwarding hierarchy (EX/MEM must take priority over MEM/WB)");
      32'd39: $display("  Detail: Failed forwarding exception for x0 (hardwired zero violated)");
      32'd40: $display("  Detail: Failed MEM stage forwarding (lw immediately followed by sw, same reg)");
      32'd41: $display("  Detail: Failed use-after-load hazard (lw immediately followed by ALU consumer)");
      32'd42: $display("  Detail: Failed branch-after-load hazard (lw immediately followed by beq)");
      32'd43: $display("  Detail: Failed lw then sw using loaded register as base address operand");
      32'd44: $display("  Detail: Failed back-to-back load stalls (lw, lw, add)");
      32'd45: $display("  Detail: Flush failed: taken branch did not squash wrong-path instruction");
      32'd46: $display("  Detail: Flush failed: jal did not squash wrong-path instruction");
      32'd47: $display("  Detail: Flush failed: not-taken branch incorrectly squashed legitimate fallthrough");
      default: $display("  Detail: Unrecognized error code. Check test program source.");
    endcase
  endtask

endmodule
