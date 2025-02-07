"""
Anharmonic free energy
"""

import os
import numpy as np


hb_J = 1.0545718e-34 #J*s
kb_J = 1.38064852*10**-23 #J/K
kb_ev = 8.6173303*10**-5 #eV/K
ev2J = 1.60217662*10**-19
J2ev = 1/ev2J
cm2hz = .02998*10**12
atomic2s = 2.418* 10**-17

def list_of_files(fpath):
    """
    Returns the list of files under in fpath directory.

    Example:

    >>> assert "README.md" in list_of_files(".")
    """
    return [
        f for f in os.listdir(fpath) if os.path.isfile(os.path.join(fpath, f))
    ]

def list_of_directories(fpath):
    """
    Returns list of folders in fpath directory

    Example:

    >>> assert "anharmonic_free_energy" in list_of_directories("..")
    """
    return list(set(os.listdir(fpath))-set(list_of_files(fpath)))

def intgrt(x, y):
    """
    Performs integration with trapezoid method

    Example:

    >>> intgrt([], [])
    (array([0]), array([0]))
    """
    I = [0]
    err = [0]
    for i in range(1, len(x)):
        I.append(np.trapz(y[:i+1], x[:i+1]))
        y_p = np.gradient(y[:i+1])
        err.append((((x[-1]-x[0])**2)/(12*len(x)**2))*(y_p[-1]-y_p[0]))

    I = np.array(I)
    err = np.array(err)
    return I, err

def lammps_log_to_U_latt(fpath, suffix='log.lammps'):
    """
    >>> lammps_log_to_U_latt('/dev/null', suffix='')
    Traceback (most recent call last):
    ...
    IndexError: list index out of range
    """
    with open(fpath+suffix, encoding='utf-8') as file:
        lines = file.readlines()

    last_step = [i-1 for i in range(len(lines)) if lines[i][:9]=='Loop time'][0]
    return float(lines[last_step].split()[1])

def ipi_harmonic_free_energy(fpath, T, nmols, U_latt):
    """
    Calculates harmonic free energy - quantum and classic - at given
    temperature at gamma.

    Reads eigenvalues in atomic units, omiting first line - ipi format.
    """
    file = open(fpath)
    lines = file.readlines()[1:]
    file.close()

    omega_kw = np.array(lines, float)[3:]
    omega_kw_abs = np.abs(omega_kw)
    omega = omega_kw_abs**.5

    freq = omega/(2*np.pi)
    freq =  freq  / atomic2s
    omega = freq * 2*np.pi

    Fq = []
    Fc = []
    for T_ in T:
        beta = 1/(T_*kb_J)
        Fq.append(
                np.sum(
                        hb_J*omega/2 + (beta**-1)*np.log(1-np.exp(-hb_J*omega*beta))
                        )
                )
        Fc.append(
                np.sum(
                        np.log(beta*hb_J*omega)/beta
                        )
                )
    return np.asanyarray(Fq)*J2ev/nmols + U_latt, np.asanyarray(Fc)*J2ev/nmols + U_latt

#calculates harmonic freee energy - quantum and classic - at given temperature
#reads eigenvalues in atomic units, omiting first line - ipi format
def phonopy_harmonic_free_energy(fpath, T, nmols, U_latt):
    file = open(fpath)
    lines = file.readlines()[3:]
    file.close()

    data = np.array([l.split() for l in lines], float)
    f = data[:,0]*cm2hz
    omega = f * 2*np.pi
    dos = data[:,1]

    Fq = []
    Fc = []
    for T_ in T:
        beta = 1/(T_*kb_J)
        Fq.append(
                np.sum(
                        dos*(
                                hb_J*omega/2 + (beta**-1)*np.log(1-np.exp(-hb_J*omega*beta))
                                )
                        )
                )
        Fc.append(
                np.sum(
                        dos*(
                                np.log(beta*hb_J*omega)/beta
                                )
                        )
                )
    return np.asanyarray(Fq)*J2ev/nmols + U_latt, np.asanyarray(Fc)*J2ev/nmols + U_latt

def _error_from_u(u):
    ug = np.gradient(u)
    c = []
    for i in range(1000):
        t1 = np.arange(0, len(ug)-i,1)
        t2 = np.arange(i, len(ug),1)
        c.append(np.sum(ug[t1]*ug[t2]))
    c = np.array(c)
    c = c/c[0]
    c = c*np.sign(c)
    c_trs = np.sum(c>.1)
    N_independent = len(u)/c_trs
    return np.std(u)/(N_independent**.5)

#reads md temperature and potential energy from simulation.out files
#within subfolders in folder 'fpath'
#steps_excluded is number of initial excluded steps
#returns temperature in K and potential energy in eV
#both quantities are sorted with respect to the temperature
def ipi_md_potential(fpath, nmols, bexclude=1000):
    subfolders = np.array(list_of_directories(fpath))
    sub = np.array(subfolders, int)
    idx = np.argsort(sub)
    subfolders = subfolders[idx]

    T = []
    U = []
    err = []
    for folder in subfolders:
        fpath_ = fpath+folder
        file = open(fpath_+'/simulation.out')
        lines = file.readlines()
        file.close()
        head = [l for l in lines[:20] if l[0]=='#']
        lines = lines[len(head):]
        head = [h.split('-->')[1] for h in head]
        head = [h.split(' : ')[0] for h in head]
        data_matrix = np.array([l.split() for l in lines], float)[bexclude:,:]

        T.append(np.mean(data_matrix[:,3]))
        U.append(np.mean(data_matrix[:,5]))
        err.append(
                _error_from_u(data_matrix[:,5])
                )
    return (
        np.asanyarray(T), np.asanyarray(subfolders, float),
        np.asanyarray(U)/nmols, np.asanyarray(err)/nmols
    )

#returns harmonic potential energy for given nuner of atoms
def harmonic_potential_energy(T,N):
    return J2ev*(3*N-3)*kb_J*T/2

#reruns anahrmonic energy
def anharmonic_energy(U_md, U_harm, U_latt):
    return U_md - U_harm - U_latt

#returns integrated anharmonic energy
def integrated_anharmonic_energy(T, U_anharm, U_err):
    x = np.log(T/T[0])
    y = U_anharm/np.exp(x)/T[0]/kb_ev
    y_err = U_err/np.exp(x)/T[0]/kb_ev
    integral = intgrt(x, y)
    int_err = intgrt(x, y_err)
    return integral[0], integral[1], int_err[0]

#returns temperature and potential energy ffrom FF->DFT calculation
def ipi_to_two_potentials(path, cut=200):
    file = open(path)
    lines = file.readlines()[1:]
    file.close()

    idx = [i for i in range(len(lines)) if lines[i][0]=='#'][-1]+1
    lines = lines[idx:]

    data = np.array([l.split() for l in lines], float)
    time = data[cut:, 1]
    pot_1 = data[cut:, 7]
    pot_2 = data[cut:, 8]
    pot_1_er = _error_from_u(pot_1)
    pot_2_er = _error_from_u(pot_2)

    return time, pot_1, pot_2, pot_1_er, pot_2_er

def integrated_ff_2_dft(fpath, nmols):
    ff_dft_subf = list_of_directories(fpath)
    ff_dft_du = []
    ff_dft_du_err = []
    _lambda = []
    for subf in ff_dft_subf:
        time, pot_1, pot_2, pot_1_er, pot_2_er = ipi_to_two_potentials(fpath+subf+'/simulation.out')
        ff_dft_du_err.append((pot_1_er + pot_2_er)/2)
        ff_dft_du.append(np.mean(pot_2 - pot_1)/nmols)
        _lambda.append(float(subf))

    idx = np.argsort(_lambda)
    _lambda = np.array(_lambda)[idx]
    ff_dft_du = np.array(ff_dft_du)[idx]
    ff_dft_du_err = np.array(ff_dft_du_err)[idx]
    lambda_av = np.mean(np.gradient(_lambda))

    F_ff_dft, F_ff_dft_err_int = intgrt(_lambda, ff_dft_du/lambda_av)
    F_ff_dft_err_md, _a = intgrt(_lambda, ff_dft_du_err/lambda_av)
    return F_ff_dft, F_ff_dft_err_md, F_ff_dft_err_int

class fe_sample:
    def __init__(
            self,
            ulatt_fpath, ulatt_nmols,
            md_fpath, md_nmols,
            u_harm_natoms, u_harm_nmols,
            fharm_fpath_phonopy, fharm_nmols_phonopy,
            fharm_fpath_ipi, fharm_nmols_ipi,
            ff_dft_fpath, ff_dft_nmols,
            ):
        self.__ulatt_fpath = ulatt_fpath
        self.__ulatt_nmols = ulatt_nmols
        self.__md_fpath = md_fpath
        self.__md_nmols = md_nmols
        self.__u_harm_natoms = u_harm_natoms
        self.__u_harm_nmols = u_harm_nmols
        self.__fharm_fpath_phonopy = fharm_fpath_phonopy
        self.__fharm_nmols_phonopy = fharm_nmols_phonopy
        self.__fharm_fpath_ipi = fharm_fpath_ipi
        self.__fharm_nmols_ipi = fharm_nmols_ipi
        self.__ff_dft_fpath = ff_dft_fpath
        self.__ff_dft_nmols = ff_dft_nmols

        #read lattice energy
        self.U_latt = lammps_log_to_U_latt(
            self.__ulatt_fpath
        )/self.__ulatt_nmols

        #read temperature and u_md
        self.T, self.Tf, self.u_md, self.u_md_err = ipi_md_potential(
                self.__md_fpath,
                self.__md_nmols,
                bexclude=1000,
                )

        ###calculate harmonic free energy, quantum and classical###
        self.F_harm_q_ipi, self.F_harm_c_ipi = ipi_harmonic_free_energy(
                self.__fharm_fpath_ipi,
                self.Tf,
                self.__fharm_nmols_ipi,
                self.U_latt,
                )
        self.F_harm_q_phonopy, self.F_harm_c_phonopy = phonopy_harmonic_free_energy(
                self.__fharm_fpath_phonopy,
                self.Tf,
                self.__fharm_nmols_phonopy,
                self.U_latt,
                )


        ###calculatin angarmonic free energy##
        #calculating anharmonic integral
        potential_energy = harmonic_potential_energy(
            self.Tf, self.__u_harm_natoms
        )
        self.u_harm = potential_energy/self.__u_harm_nmols
        self.u_anharm = anharmonic_energy(self.u_md, self.u_harm, self.U_latt)
        (
            self.anharm_integral,
            self.anharm_integral_err,
            self.anharm_integral_md_err,
        ) = integrated_anharmonic_energy(self.Tf, self.u_anharm, self.u_md_err)

        #calculating harmonic part
        self.f_harm_part = (self.F_harm_c_ipi[0]-self.U_latt)*self.Tf/self.Tf[0]

        #calculating kinetic part
        self.f_class_nucl = kb_ev*self.Tf*(
            3*self.__u_harm_natoms-3
        )*np.log(self.Tf/self.Tf[0])/self.__u_harm_nmols

        #calculating classical anharmonic free energy
        self.F_anh_c = (
            self.U_latt + self.f_harm_part - self.f_class_nucl
            - self.anharm_integral*kb_ev*self.Tf
        )

        #calculating quantum anharmonic free energy
        self.F_anh_q = self.F_anh_c + self.F_harm_q_ipi - self.F_harm_c_ipi

        #calculating the error of the TI parht of anharmonic free energy
        self.F_err_int_ti = self.Tf*self.anharm_integral_err*kb_ev

        #calculating the error of the TI parht of anharmonic free energy
        self.F_err_md = self.Tf*self.anharm_integral_md_err*kb_ev

        self.F_anh_err = (
                np.absolute(self.F_err_md) +
                np.absolute(self.F_err_int_ti)
                )
        self.F_ff_dft, self.F_ff_dft_err_md, self.F_ff_dft_err_int = integrated_ff_2_dft(
                self.__ff_dft_fpath,
                self.__ff_dft_nmols,
                )
        self.F_ff_dft = self.F_ff_dft[-1]
        self.F_ff_dft_err_md = np.abs(self.F_ff_dft_err_md[-1])
        self.F_ff_dft_err_int = np.abs(self.F_ff_dft_err_int[-1])
