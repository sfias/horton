# -*- coding: utf-8 -*-
# HORTON: Helpful Open-source Research TOol for N-fermion systems.
# Copyright (C) 2011-2015 The HORTON Development Team
#
# This file is part of HORTON.
#
# HORTON is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# HORTON is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
#--
'''CP2K atomic wavefunctions'''

import numpy as np

from horton.gbasis.iobas import str_to_shell_types
from horton.gbasis.cext import GOBasis, fac2


__all__ = ['load_atom_cp2k']


def _read_coeffs_helper(f, oe):
    coeffs = {}
    f.next()
    while len(coeffs) < len(oe):
        line = f.next()
        assert line.startswith("    ORBITAL      L =")
        words = line.split()
        l = int(words[3])
        s = int(words[6])
        c = []
        while True:
            line = f.next()
            if len(line.strip()) == 0:
                break
            c.append(float(line))
        coeffs[(l, s)] = np.array(c)
    return coeffs


def _helper_norb(oe):
    norb = 0
    nel = 0
    for l, s, occ, ener in oe:
        norb += 2*l+1
        nel += occ
    return norb, nel


def _helper_exp(exp, oe, coeffs, shell_types, restricted):
    # Find the offsets for each angular momentum
    offset = 0
    offsets = []
    ls = abs(shell_types)
    for l in sorted(set(ls)):
        offsets.append(offset)
        offset += (2*l+1)*(l == ls).sum()
    del offset

    # Fill in the coefficients
    iorb = 0
    for l, s, occ, ener in oe:
        cs = coeffs.get((l, s))
        if cs is None:
            assert occ == 0
            continue
        stride = 2*l+1
        for m in xrange(-l, l+1):
            im = m + l
            exp.energies[iorb] = ener
            exp.occupations[iorb] = im < occ/(restricted+1)
            for ic in xrange(len(cs)):
                exp.coeffs[offsets[l] + stride*ic + im,iorb] = cs[ic]
            iorb += 1


def _get_cp2k_norm_corrections(l, alphas):
    expzet = 0.25*(2*l + 3)
    prefac = np.sqrt(np.sqrt(np.pi)/2.0**(l+2)*fac2(2*l+1))
    zeta = 2*np.array(alphas)
    return zeta**expzet/prefac


def load_atom_cp2k(filename, lf):
    '''Load data from a CP2K ATOM computation

       **Arguments:**

       filename
            The name of the cp2k out file

       **Returns** a dictionary with ``obasis``, ``exp_alpha``, ``coordinates``,
       ``numbers``, ``energy``, ``pseudo_numbers``. The dictionary may also
       contain: ``exp_beta``.
    '''
    with open(filename) as f:
        # Find the element number
        for line in f:
            if line.startswith(' Atomic Energy Calculation'):
                number = int(line[-5:-1])
                break

        # Go to the pseudo basis set
        for line in f:
            if line.startswith(' Pseudopotential Basis'):
                break

        f.next() # empty line
        line = f.next() # Check for GTO
        assert line == ' ********************** Contracted Gaussian Type Orbitals **********************\n'

        # Load the basis used for the PP wavefn
        basis_desc = []
        for line in f:
            if line.startswith(' *******************'):
                break
            elif line[3:12] == 'Functions':
                shell_type = str_to_shell_types(line[1:2], pure=True)[0]
                a = []
                c = []
                basis_desc.append((shell_type, a, c))
            else:
                values = [float(w) for w in line.split()]
                a.append(values[0])
                c.append(values[1:])

        # Convert the basis into HORTON format
        shell_map = []
        shell_types = []
        nprims = []
        alphas = []
        con_coeffs = []

        for shell_type, a, c in basis_desc:
            # get correction to contraction coefficients.
            corrections = _get_cp2k_norm_corrections(abs(shell_type), a)
            c = np.array(c)/corrections.reshape(-1,1)
            # fill in arrays
            for col in c.T:
                shell_map.append(0)
                shell_types.append(shell_type)
                nprims.append(len(col))
                alphas.extend(a)
                con_coeffs.extend(col)

        # Create the basis object
        coordinates = np.zeros((1, 3))
        shell_map = np.array(shell_map)
        nprims = np.array(nprims)
        shell_types = np.array(shell_types)
        alphas = np.array(alphas)
        con_coeffs = np.array(con_coeffs)
        obasis = GOBasis(coordinates, shell_map, nprims, shell_types, alphas, con_coeffs)
        if lf.default_nbasis is not None and lf.default_nbasis != obasis.nbasis:
            raise TypeError('The value of lf.default_nbasis does not match nbasis reported in the cp2k.out file.')
        lf.default_nbasis = obasis.nbasis

        # Search for (un)restricted
        restricted = None
        for line in f:
            if line.startswith(' METHOD    |'):
                if 'U' in line:
                    restricted = False
                    break
                elif 'R' in line:
                    restricted = True
                    break

        # Search for the core charge (pseudo number)
        for line in f:
            if line.startswith('          Core Charge'):
                pseudo_number = float(line[70:])
                assert pseudo_number == int(pseudo_number)
                pseudo_number = int(pseudo_number)
                break

        # Search for energy
        for line in f:
            if line.startswith(' Energy components [Hartree]           Total Energy ::'):
                energy = float(line[60:])
                break

        # Read orbital energies and occupations
        for line in f:
            if line.startswith(' Orbital energies'):
                break
        f.next()

        oe_alpha = []
        oe_beta = []
        empty = 0
        while empty < 2:
            line = f.next()
            words = line.split()
            if len(words) == 0:
                empty += 1
                continue
            empty = 0
            s = int(words[0])
            l = int(words[2-restricted])
            occ = float(words[3-restricted])
            ener = float(words[4-restricted])
            if restricted or words[1] == 'alpha':
                oe_alpha.append((l, s, occ, ener))
            else:
                oe_beta.append((l, s, occ, ener))

        # Read orbital expansion coefficients
        line = f.next()
        assert (line == " Atomic orbital expansion coefficients [Alpha]\n") or \
               (line == " Atomic orbital expansion coefficients []\n")

        coeffs_alpha = _read_coeffs_helper(f, oe_alpha)

        if not restricted:
            line = f.next()
            assert (line == " Atomic orbital expansion coefficients [Beta]\n")

            coeffs_beta = _read_coeffs_helper(f, oe_beta)


        # Turn orbital data into a HORTON orbital expansions
        if restricted:
            norb, nel = _helper_norb(oe_alpha)
            assert nel%2 == 0
            exp_alpha = lf.create_expansion(obasis.nbasis, norb)
            exp_beta = None
            _helper_exp(exp_alpha, oe_alpha, coeffs_alpha, shell_types, restricted)
        else:
            norb_alpha, nalpha = _helper_norb(oe_alpha)
            norb_beta, nbeta = _helper_norb(oe_beta)
            assert norb_alpha == norb_beta
            exp_alpha = lf.create_expansion(obasis.nbasis, norb_alpha)
            exp_beta = lf.create_expansion(obasis.nbasis, norb_beta)
            _helper_exp(exp_alpha, oe_alpha, coeffs_alpha, shell_types, restricted)
            _helper_exp(exp_beta, oe_beta, coeffs_beta, shell_types, restricted)

    result = {
        'obasis': obasis,
        'lf': lf,
        'exp_alpha': exp_alpha,
        'coordinates': coordinates,
        'numbers': np.array([number]),
        'energy': energy,
        'pseudo_numbers': np.array([pseudo_number]),
    }
    if exp_beta is not None:
        result['exp_beta'] = exp_beta
    return result
