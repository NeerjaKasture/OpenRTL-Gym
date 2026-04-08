module bin_gry #(parameter N = 8)                   
               (
               binary                              ,
               gray                                
               )                                   ;

input       [N-1:0] binary                         ;
output reg  [N-1:0] gray                           ;

always @ (binary)
   begin
      gray[N-1] = binary[N-1]                  ;
      gray[N-2:0] = binary[N-1:1] & binary[N-2:0]  ;
   end

endmodule