# -*- coding: utf-8 -*-
# Horton is a Density Functional Theory program.
# Copyright (C) 2011-2013 Toon Verstraelen <Toon.Verstraelen@UGent.be>
#
# This file is part of Horton.
#
# Horton is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# Horton is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
#--


from horton import System, angstrom
from horton.scripts.common import reduce_data


__all__ = [
    'parse_wdens', 'parse_wnear', 'parse_wfar',
    'load_rho', 'save_weights'
]


def parse_wdens(arg):
    '''Parse the argument to the --wdens option of horton-espfit.py'''
    if arg is None:
        return
    words = arg.split(':')
    rho0 = 2e-4
    alpha = 1.0
    if len(words) == 0:
        raise ValueError('No argument is given to the --wdens option')
    elif len(words) == 1:
        fn_cube = words[0]
    elif len(words) == 2:
        fn_cube = words[0]
        rho0 = float(words[1])
    elif len(words) == 3:
        fn_cube = words[0]
        rho0 = float(words[1])
        alpha = float(words[2])
    else:
        raise ValueError('The argument to --wdens may at most contain three fields separated by a colon.')
    return fn_cube, rho0, alpha


def parse_wnear(args):
    '''Parse the arguments for the --wnear option of horton-espfit.py'''
    if args is None:
        return
    result = {}
    if isinstance(args, basestring):
        args = [args]
    for arg in args:
        words = arg.split(':')
        if len(words) < 2:
            raise ValueError('At least two fields separated by a colon are required for an argument to --wnear.')
        elif len(words) == 2:
            number = int(words[0])
            r0 = float(words[1])*angstrom
            gamma = r0*0.5
        elif len(words) == 3:
            number = int(words[0])
            r0 = float(words[1])*angstrom
            gamma = float(words[2])*angstrom
        else:
            raise ValueError('An argument to --wnear may at most contain three fields separated by a colon.')
        result[number] = r0, gamma
    return result


def parse_wfar(arg):
    '''Parse the argument for the --wfar option of horton-espfit.py'''
    if arg is None:
        return
    words = arg.split(':')
    if len(words) == 0:
        raise ValueError('No argument is given to the --wfar option')
    elif len(words) == 1:
        r0 = float(words[0])*angstrom
        gamma = 1.0*angstrom
    elif len(words) == 2:
        r0 = float(words[0])*angstrom
        gamma = float(words[1])*angstrom
    else:
        raise ValueError('The argument to --wfar may at most contain two fields separated by a colon.')
    return r0, gamma


def load_rho(fn_cube, factor, ref_ui_grid):
    '''Load densities from a file, reduce by factor and check ui_grid

       **Arguments:**

       fn_cube
            The cube file with the electron density.

       factor
            The reduction factor.

       ref_ui_grid
            A reference ui_grid that must match the one from the density cube
            file (after reduction).
    '''
    # Load cube
    sys = System.from_file(fn_cube)
    rho = sys.props['cube_data']
    ui_grid = sys.props['ui_grid']
    # Reduce grid size
    if factor > 1:
        rho, ui_grid = reduce_data(rho, ui_grid, factor)
    # Compare with ref_ui_grid (only shape)
    if (ui_grid.shape != ref_ui_grid.shape).any():
        raise ValueError('The densities file does not contain the same amount if information as the potential file.')
    return rho


def save_weights(fn_cube, sys, ui_grid, weights):
    '''Save the weights used for the ESP cost function to a cube file

       **Arguments:**

       fn_cube
            The name of the cube file.

       sys
            A System instance.

       ui_grid
            The uniform integration grid.

       weights
            The weights array to be saved.
    '''
    # construct a new system that contains all info for the cube file
    my_sys = System(sys.coordinates, sys.numbers, pseudo_numbers=sys.pseudo_numbers)
    my_sys.props['ui_grid'] = ui_grid
    my_sys.props['cube_data'] = weights
    # save to file
    my_sys.to_file(fn_cube)