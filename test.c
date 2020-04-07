#include <stdint.h>
#include <stdio.h>
#include "thermistor_table.h"

// edit as needed to cover the range of your expected ADC values
// compile with:
//
//     gcc -o test test.c thermistor_table.c
//
// run it and verify the output curve is correct

int main(int argc, char *argv[])
{
    for (int adc = 0; adc < 1024; adc += 5)
    {
        printf("%d, %d\n", adc, adc_to_temp(adc));
    }
    return 0;
}

