#!/usr/bin/env python
#
# MIT License
#
# Copyright (c) 2020 Joseph Kroesche
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

import math
import argparse
import json
import datetime

# This python program is used to generate a C-language thermistor temperature
# calculation program. It is intended for use by small microcontrollers
# with limited memory and compute resources. For example 8051 or AVR MCUs.
# This program pre-computes a lookup table for a given thermistor circuit.
# The lookup table covers a certain temperature range and step size. This
# The algorithm uses the ADC reading of the temperature sensor to find a
# segment in the lookup table, and then linear-interpolates between the two
# points to come up with a temperature. Compared to peforming run-time
# thermistor algorithm calculations, this method makes temperature calculation
# much easier for the MCU, while still retaining the non-linear
# resistance-to-temperature curve of the thermistor. You can make the curve
# more accurate by using more steps, but that will also create a bigger table
# using more flash memory of the MCU.
#
# The function will interpolate beyond the boundaries of the table, using
# the slope of the edge segment. This will return a sane-looking temperature
# that varies linearly with ADC value, but the error will grow increasingly
# large the futher the input is outside the range of the table.
#
# The input for this script is a json file that describes the thermistor and
# the sensing circuit. An example is shown below, with annotations in
# square brackets:
#
# {
#    "board": "diyBMSv4 prototype (oshpark purple) board",  [comment]
#    "thermistor": "Sunlord SDNT2012X473F4150FTF",          [mfr and part #]
#    "Tstart": 0,           [starting temperature for table]
#    "Tstop": 80,           [ending temperature for table (exclusive)]
#    "Tstep": 8,            [temperature step size]
#    "Tnominal": 25,        [thermistor nominal temperature]
#    "Rnominal": 47000,     [thermistor nominal resistance]
#    "Rpulldown": 47000,    [pulldown resistor value]
#    "beta": 4150,          [thermistor B-value]
#    "counts": 1023         [full scale ADC counts]
# }
#
# Assumptions:
# * ADC is unsigned, single ended input
# * thermistor is NTC type
# * thermistor is in a divider circuit with a "pulldown" resistor
# * top of thermistor divider is attached to ADC voltage reference
# * bottom of pulldown is ground
# * ADC measurement is between thermistor and pulldown
#
# This program generates a ready-to-compile C header file and function
# source code.
#
# Sites I found useful when developing this:
#
# https://blog.stratifylabs.co/device/2013-10-03-ADC-Thermistor-Circuit-and-Lookup-Table/
# https://en.wikipedia.org/wiki/Thermistor#B_or_β_parameter_equation
# https://www.electro-tech-online.com/tools/thermistor-resistance-calculator.php
#

license_block = (
"""/******************************************************************************
 * SPDX-License-Identifier: MIT
 *
 * Copyright (c) {:d} Joseph Kroesche
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to
 * deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
 * sell copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 *
 *****************************************************************************/

""")

header_open = """#ifndef __THERMISTOR_TABLE_H__
#define __THERMISTOR_TABLE_H__

"""

header_close = """#endif

/** @} */
"""

parms_block = (
"""/** @addtogroup therm Thermistor
 *
 * This file was generated by https://github.com/kroesche/thermistor_lookup
 *
 * Generated on {:s},<br/>
 * for a thermistor circuit with the following parameters:
 *
 * |Parameter |Value                         |
 * |----------|------------------------------|
 * |Input File|{:<30s}|
 * |Board     |{:<30s}|
 * |Thermistor|{:<30s}|
 * |Tstart    |{:<30d}|
 * |Tstop     |{:<30d}|
 * |Tstep     |{:<30d}|
 * |Tnominal  |{:<30d}|
 * |Rnominal  |{:<30d}|
 * |Rpulldown |{:<30d}|
 * |beta      |{:<30d}|
 * |counts    |{:<30d}|
 *
 * @{{
 */

""")

function_declaration = (
"""#ifdef __cplusplus
extern "C" {
#endif

/**
 * Get temperature in C from ADC input.
 *
 * @param adc ADC counts for the temperature sensor
 *
 * Calculates the temperature in C from a temperature sensor ADC value.
 * The calculation uses a lookup table generated for a specific thermistor
 * circuit. If the input is outside the range of the pre-computed lookup table,
 * it interpolates linearly beyond the table, with an increasing amount of
 * error the further outside the table range.
 */
extern int16_t adc_to_temp(uint16_t adc);

#ifdef __cplusplus
}
#endif

""")

function_definition = (
"""// Calculate temperature using lookup table.
// See header file for API description
int16_t adc_to_temp(uint16_t adc)
{
    uint16_t idx;
    int16_t adc0;
    int16_t adc1;
    int16_t temp0 = 0; // prevent g++ warning

    if (adc < therm_table[0])
    {
        adc0 = therm_table[0];
        adc1 = therm_table[1];
        temp0 = T_AT_IDX(0);
    }
    else if (adc >= therm_table[T_LAST_IDX])
    {
        adc0 = therm_table[T_LAST_IDX - 1];
        adc1 = therm_table[T_LAST_IDX];
        temp0 = T_AT_IDX(T_LAST_IDX - 1);
    }

    else
    {
        for (idx = 0; idx < T_LAST_IDX; ++idx)
        {
            adc0 = therm_table[idx];
            adc1 = therm_table[idx + 1];
            if (adc < adc1)
            {
                temp0 = T_AT_IDX(idx);
                break;
            }
        }
    }

    int16_t delta = adc - adc0;
    uint16_t range = adc1 - adc0;
    int16_t half_digit = range >> 1;

    int16_t temp = delta * T_STEP + half_digit;
    temp /= range;
    temp += temp0;

    return temp;
}
""")

# find thermistor resistance at a given temperature
def temp_to_R(r0, t0, beta, temp):
    expo = (1.0 / temp) - (1.0 / t0)
    expo *= beta
    rout = r0 * math.exp(expo)
    return rout

# find ADC counts for a given thermistor resistance
def R_to_counts(rtherm, rpd, rez):
    counts = rez * rpd / (rtherm + rpd)
    return counts

parser = argparse.ArgumentParser(description="Generate Thermistor Lookup Table")
parser.add_argument("jsonfile", help="JSON file with parameters")
args = parser.parse_args()

# read the json file and convert fields to variables
with open(args.jsonfile, "r") as jsonfile:
    parms = json.load(jsonfile)
    Tstart = parms['Tstart']
    Tstop = parms['Tstop']
    Tstep = parms['Tstep']
    Tnominal = parms['Tnominal']
    Rnominal = parms['Rnominal']
    Rpulldown = parms['Rpulldown']
    beta = parms['beta']
    counts = parms['counts']
    board = parms['board']
    thermistor = parms['thermistor']

    # fill in the variable data in the parameters comment block
    rendered_parms_block = parms_block.format(str(datetime.datetime.now()),
        args.jsonfile, board, thermistor,
        Tstart, Tstop, Tstep, Tnominal, Rnominal, Rpulldown, beta, counts)

    # generate the header file. no other calculation needed
    with open("thermistor_table.h", "wt") as hfile:
        hfile.write(license_block.format(datetime.date.today().year))
        hfile.write(header_open)
        hfile.write(rendered_parms_block)
        hfile.write(function_declaration)
        hfile.write(header_close)

    # generate the start of the C source file
    with open("thermistor_table.c", "wt") as cfile:
        cfile.write(license_block.format(datetime.date.today().year))
        cfile.write("#include <stdint.h>\n\n")
        cfile.write(rendered_parms_block)
        cfile.write("static const uint16_t therm_table[] =\n{\n")

        # generate the lookup table contents as C array
        idx = 0
        for temp in range(Tstart, Tstop, Tstep):
            newr = temp_to_R(Rnominal, Tnominal+273, beta, temp+273)
            adc = R_to_counts(newr, Rpulldown, counts)
            cfile.write("   {:4d}, // [{:2d}] C={:2d} R={:d}\n".format(
                int(round(adc)), idx, int(round(temp)), int(round(newr))))
            idx += 1
        cfile.write("};\n\n")

        # generate the C macros used by the function
        if Tstart == 0:
            cfile.write("#define T_AT_IDX(idx) ((idx) * {:d})\n".format(Tstep))
        else:
            cfile.write("#define T_AT_IDX(idx) ({:d} + ((idx) * {:d}))\n".format(Tstart, Tstep))
        cfile.write("#define T_STEP ({:d})\n".format(Tstep))
        cfile.write("#define T_LAST_IDX ({:d})\n\n".format(idx - 1))

        # generate the C function into the source file
        cfile.write(function_definition)
