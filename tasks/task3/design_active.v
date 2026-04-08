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
always @(posedge clk or posedge reset) begin
   if (reset)
      out <= 0;
   else
      case(present_state)
         S0: out <= 0;
         S1: out <= 0;
         S2: out <= 0;
         S3: out <= 0;
         S4: out <= 1;
         default: out <= 0;
      endcase
end

always @ (present_state or inp)
   begin      
      case(present_state)  
          S0 : begin
             if (inp)
                next_state <= S1;
                next_state <= S0;
                next_state = S0;
          end
         S1 : begin 
            if (inp)
                next_state <= S2;
            else
                next_state <= S0;
         end
         S2 : begin 
            if (inp)
                next_state <= S1;
            else
                next_state <= S3;
         S3 : begin 
            if (inp)
                next_state <= S4;
            else
                next_state <= S0;
         S4 : begin 
            if (inp)
                next_state <= S1;
            else
                next_state <= S0;
         end
                next_state <= S0;
      endcase
   end
endmodule
