## Issue (hgrecco/pint)

Enable Mixed Unit Operations with Log Units [0dBm -10 dB = -10dBm] 
In electrical engineering, quantities with logarithmic units such as dB and dBm are "summed" or "subtracted" although having different dimensionalities (which is forbidden for base units in pint). It would be nice if pint could support such operations.

**Example 1: dB and dBm**
Let's consider a transmitter that generates a signal of 10 dBm. This signal goes through a channel that has an attenuation of -20 dB. The output power we expect is:

`Q(10, ureg.dBm) - Q(20, ureg.dB) = Q(-10, ureg.dBm)`

"Under the hood", the algebraic sum between dBm and dB is a product of two quantities  in linear units (power and transmission probability), so the "difference" does not present a problem.
When converting the logarithmic units to base units, the operation becomes:

`Q(10, ureg.dBm) -> 1e1 mW`
`Q(-20, ureg.dB) -> 1e-2`

the sum in logarithmic units becomes a product in linear units, and the result is a power:

`Q(10, ureg.dBm) + Q(-20, ureg.dB) -> 1e1 mW * 1e-2 = 1e-1 mW`

The output power is converted back into a logarithmic unit, if that unit is available:

`1e-1 mW -> Q(-10, ureg.dBm)`

Here you see that the sum of dBm and dB gives a result in dBm and the result looks like a difference.

**Example 2: dB/km * km**
A related operation could pop-up when dealing with a channel with -10 dB/km losses, which attenuates the power of a signal by a factor of 10% for every km of propagation. If the channel is 3 km long one would get.

`Q(-10, ureg.dB / ureg.km) * Q(3, ureg.km)`

Pint can handle the computation with linear units in three steps:

_Step#1:_ convert the log unit into base unit, which is from dB/km to dimensionless/km:
`Q(-10, ureg.dBm/ ureg.km) -> 1e-1 ureg.km^-1`

_Step#2:_ change the product into an exponentiation
`Q(-10, ureg.dB / ureg.km) * Q(3, ureg.km) -> (1e-1) ** (Q(3, ureg.km) / ureg.km)= 1e-3`

_Step#3:_ go back into a logarithmic unit, if that is available:
    `1e-3 -> Q(-30, ureg.dB)`

Also here the exponentiation in linear units looks as a product in log units.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
