module moore_ol(
        inp,
        clk,
        reset,
        out
        );

input       inp, clk, reset;
output reg  out;
parameter   S0 = 0 , S1 = 1 , S2 = 2 , S3 = 3, S4 = 4;
reg         [2:0] present_state, next_state;

always @ (posedge clk or posedge reset)
   begin
      if(reset)
         present_state <= S0;
      else    
         present_state <= next_state;
   end             

always @ (present_state or inp)
   begin      
      case(present_state)  
         S0 : begin
            if (inp)
               next_state = S1;
            else
               next_state = S0;
            out = 0;
         end
         S1 : begin 
            if (inp)
               next_state = S2;
            else
               next_state = S0;
            out = 0;
         end
         S2 : begin 
            if (inp)
               next_state = S2;  // FIX: If current state is S2 (seen '11') and input is '1', the sequence becomes '111'. The longest suffix of '111' that is also a prefix of '1101' is '11'. So, the FSM should remain in S2. It was incorrectly transitioning to S1.
            else
               next_state = S3;
            out = 0;
         end 
         S3 : begin 
            if (inp)
               next_state = S4;
            else
               next_state = S0;
            out = 0;
         end 
         S4 : begin 
            if (inp)
               next_state = S2;
            else
               next_state = S0;
            out = 1;
         end
         default: next_state = S0;
      endcase
   end
endmodule