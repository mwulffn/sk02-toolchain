The SK-02 computer has 2 stack registers of 16 bits each.

The upper 8 bits of each register are fixed and set by dipswiches and the lower 8 bits are controlled by two 4-bit binary counters (74HC191's) and the counters are set to 0x00 or 0xFF when te CPU is reset depending on the settings of switch 2 and 3 of dipswitch SW-3.

The 2 registers are used for different purposes:

Stack 0 is used as a link register for return addresses for subroutine calls (for the GOSUB and RETURN opcodes). For each gosub command 2 bytes are used for the return address, thus the CPU can handle 127 nested subroutine calls before the link register stack overflows.
Stack 1 is a general purpose stack register and are used by the various Push and POP opcodes
Depending on setting of switch 2 and 3 of dipswitch SW-3 the counters (low byte of the stack address) either start at 0x00 or 0xFF when reset. Additionally the settings of switch 1 determines if the stack module should use 8 or 16 bit data bus. In the former case switch 0 determines if shift up or shift down command should also ouptut the content of the (fixed) high byte of the accress to the data bus. In the current configuration of the SK-+2 computer, SW3 is set to on - off - on - on, that is output high byte on push/pop, use 8 bit data bus and use 0x00 as reset value for low byte of both stacks.

Stack overflow (or underflow) are signalled by the 2 LEDs D17 and D18 connected to output J2 which should be conected to 2 of the inputs on the J-9 connector on the Aux-GPIO board or alternatively, if the hardware interupt board is installed, it could be connected to 2 of the hardwar interupt inputs. In this case the intrupt handler should behave sensibly if it process an interupt and one of the stack over / underflow bits are set.


