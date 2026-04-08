module bin_gry #(parameter N = 8)                   
       (
       input       [N-1:0] binary,
       output reg  [N-1:0] gray
       );

always @ (*) // Use '*' for combinational logic sensitivity list
   begin
      // The most significant bit (MSB) of the Gray code is the same as the MSB of the binary code.
      gray[N-1] = binary[N-1];

      // For all other bits, the i-th Gray code bit is the XOR of the i-th binary bit and the (i+1)-th binary bit.
      // gray[i] = binary[i+1] ^ binary[i]
      for (integer i = 0; i < N - 1; i = i + 1) begin
         gray[i] = binary[i+1] ^ binary[i];
      end
   end

endmodule