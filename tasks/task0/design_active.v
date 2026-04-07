module half_adder(
    input a, b,
    output sum, carry
);
    assign sum = a ^ b;
    assign carry = a & b; // Changed 'and' to '&' for the bitwise AND operator
endmodule