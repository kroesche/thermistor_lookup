Thermistor Lookup Table Generator
=================================

This python script is used to generate a ready-to-compile C source and
header file containing a thermistor temperature calculation algorithm, using
a lookup table method. It is intended for use by small resource-constrained
microcontrollers.

LICENSE: [MIT](https://opensource.org/licenses/MIT)

How to Use
----------

1. create and edit json file with your table parameters (see example.json)
2. run the generator script
3. copy the generated source files (.c and .h) to your project
4. call the function from your program when you need to compute the
   temperature from ADC value

### Assumed Circuit

```

            Thermistor
    Vref ----/\/\/\/----+
                        |
                        +----> to ADC input
                        |
    GND  ----/\/\/\/----+
            Rpulldown

```

### JSON File

| Field     | Description                                      |
|-----------|--------------------------------------------------|
| board     | name of your board or project (cosmetic)         |
| thermistor| thermistor part number (cosmetic)                |
| Tstart    | lowest temperature of table                      |
| Tstop     | highest temperature of table (exclusive)         |
| Tstep     | temperature step size                            |
| Tnominal  | thermistor nominal temperature (from data sheet) |
| Rnominal  | thermistor nominal resistance (from data sheet)  |
| Rpulldown | value of the pull-down resistor                  |
| beta      | thermistor B value (from data sheet)             |
| counts    | max counts of the ADC                            |

**NOTES:**

1. All temperatures are in C.
2. Cosmetic fields are shown in generated comments but have no other function.
3. The size of the table is adjusted by tweaking `Tstart`, `Tstop`, and
   `Tstep`. You can adjust the tradeoff between how well the curve fits and
   how much memory is needed for the table.
4. For values outside the range of the lookup table, the algorithm interpolates
   linearly, using the end segments. The error of the calculated temperature
   will increase the further the actual measurement is outside the table
   range.

### Generating the Files

Assumes python3.

    ./generator myboard.json

### Using the Files

Add the source files to your project. Include the header where needed. Call
the function when needed to compute temperature from ADC value.

#### API

| API        | Definition                                               |
|------------|----------------------------------------------------------|
| prototype  | `int16_t adc_to_temp(uint16_t adc);`                     |
| parm `adc` | unsigned 16-bit ADC value for thermistor circuit voltage |
| returns    | signed 16-bit temperature in C                           |

#### Usage

```c
#include <stdint.h>
#include "thermistor_table.h"
...

...
uint16_t adcval = read_adc(TEMP_SENSOR_CHANNEL);
int16_t temp_in_C = adc_to_temp(adcval);
...
```

Testing
-------

You can do a quick check of the lookup table using the simple `test.c`
program. Edit the source of `test.c` to cover the range you want to check.
Then compile and run with:

    gcc -o test test.c thermistor_table.c
    ./test

It will print a table. You can examine the output and verify the ADC to
temperature curve is correct.
