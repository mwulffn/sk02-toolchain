The A and B register board consists of two 8-bit registers each consisting of two 74LS194 4-bit shift registers with parallel load. These IC's was one of the few types I could not find in a CMOS version and thus had to use normal 74LSxx chips.

The use of the shift register IC's instead of mere D-flip-flops on the A and B rigisters enable the SK-02 computer to do bitshift in both directions for both the A and B register individually. This makes it easy to do multiplication or division as a bitshift corresponds to divide by 2 or multiply by 2 (depending on direction).

Each register has two outputs. One directly to the ALU and one through a 74HC541 buffer to the data bus.

In the case of the A-reigster, it also has the option to output the inverted value by using the single 74HS540 inverting buffer IC. This enables the option to invert the content of the A register by outputting the inverse value to the bus and reading the value in to the A register again. This function was handled by the ALU in the SK-01 computer but the SK-02 handles this by the A register board itself.

In order to facilitate 16 bit opreations an additional input (handled by pin 4 on J6) enables the high byte of the A register to be used for shift in on the low bit of rigeister B and vise versa. This effectively causes the A and B register to behave as a single 16 bit register for shift operations. In the actual opcodes for the SK-02 compuer this is handled by utilising the SUBTRACT control line to enable 16 bit shift operations.

The C and D register board was the first board I designed with KiCAD and got manufactured. As such it has the least changes from the similar board on the SK-01 computer.

It consists of 2 general prupose 8-bit registers using 74ATC835 8-bit D-flip-flops with enable and 74HC541 buffer IC's for output (in order to be able to show the content of the registers using LED's).

In order to reduce the load on the data bus, a single 74HC541 is used to buffer the data bus for the inputs of the 74ATC825's. However this feature was likely not nescesarry.

The board also conatins 3 special outputs for putting 0x00, 0x01 or 0xFF on to the data bus. This is handled by a single 74HC541 buffer in connection with a pair of AND gates.


The board for the E,F,G and H registers is also designed to be able to be used with a true 16 bit data bus. As with the instruction counter board, jumpers determine the bus mode. If jumpers J1,J2,J3 and J4 are closed the board is operating in 16 bit mode and 8 bit mode if they are open.

In 16 bit mode, the G and H registers are used as the low bytes of the E and F registers effectiively turning the board into a dual 16-bit register board.

As with the C and D registers, each register consists of a 74ATC825 register and a 74HC541 output buffer with LED's showing the state of the register.


