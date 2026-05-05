from z3 import *
d, a, t, v_i, v_f = Reals('d a t v_i v_f')

equations = [
    d == v_i * t + (a*t**2)/2,
    v_f == v_i + a*t,
]

problem = [
    v_i == 0,
    t == 4.10,
    a==6
]

solve(equations + problem)

set_option(rational_to_decimal = True)

solve(equations + problem)
