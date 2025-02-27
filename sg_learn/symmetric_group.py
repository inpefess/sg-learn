"""
    Machine learning proofs for classification of nilpotent semigroups. 
    Copyright (C) 2021  Carlos Simpson

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import torch

from constants import Dvc
from utils import CoherenceError, arangeic, binaryzbatch, itp, zbinary


class SymmetricGroup:
    def __init__(self, p):
        #
        if p < 1:
            print("can't initialize a symmetric group with size", p)
            raise CoherenceError("exiting")
        if p > 9:
            print(
                "symmetric group size",
                p,
                "is probably going to cause a memory overflow somewhere",
            )
            raise CoherenceError("exiting")
        #
        self.p = p
        # self.subgroups_max = subgroups_max # this is not currently used
        #
        self.gtlength = 1
        for i in range(self.p):
            self.gtlength *= i + 1
        #
        self.grouptable = self.makegrouptable()
        self.gtbinary = self.makegrouptablebinary()
        # self.multiplicationtable = self.makemult()
        # self.inverse = self.makeinverse()
        self.inversetable = self.makeinversetable()
        #

    def symmetricgrouptable(self, k):
        assert k > 0
        if k == 1:
            sgt = torch.zeros((1), dtype=torch.int64, device=Dvc)
            return 1, sgt
        length_prev, sgtprev = self.symmetricgrouptable(k - 1)
        length = length_prev * k
        krange = torch.arange(
            (k), dtype=torch.int64, device=Dvc
        )  # same as arangeic(k)
        krangevx = krange.view(k, 1).expand(k, length_prev)
        krangevx2 = krange.view(k, 1, 1).expand(k, length_prev, k - 1)
        #
        sgtprev_vx = sgtprev.view(1, length_prev, k - 1).expand(
            k, length_prev, k - 1
        )
        #
        krange1vxr = krange.view(k, 1).expand(k, k).reshape(k * k)
        krange2vxr = krange.view(1, k).expand(k, k).reshape(k * k)
        gappedtablev = krange2vxr[(krange1vxr != krange2vxr)]
        gappedtable = gappedtablev.view(k, k - 1)
        #
        afterpart = gappedtable[krangevx2, sgtprev_vx]
        beforepart = krange.view(k, 1, 1).expand(k, length_prev, 1)
        newtablev = torch.cat((beforepart, afterpart), 2)
        newtable = newtablev.view(length, k)
        return length, newtable

    def makegrouptable(self):
        length, table = self.symmetricgrouptable(self.p)
        assert length == self.gtlength
        # print("making group table for symmetric group, as an array of shape",table.size())
        return table

    def findpermutation(self, batchlength, vector):
        vectorvx = vector.view(batchlength, 1, self.p).expand(
            batchlength, self.gtlength, self.p
        )
        grouptablevx = self.grouptable.view(1, self.gtlength, self.p).expand(
            batchlength, self.gtlength, self.p
        )
        detection = (vectorvx == self.grouptable).all(2)
        values, permutation = torch.max((detection.to(torch.int)), 1)
        assert (values == 1).all(0)
        return permutation

    def makemult(self):
        if self.p > 7:
            print(
                "multiplication table for symmetric group of size",
                self.p,
                "would probably crash",
            )
            raise CoherenceError("exiting")
        print("setting up multiplication table...", end=" ")
        mult = torch.zeros(
            (self.gtlength, self.gtlength), dtype=torch.int64, device=Dvc
        )
        for x in range(self.gtlength):
            xvector = self.grouptable[x]
            comptable = xvector[self.grouptable]
            mult[x, :] = self.findpermutation(self.gtlength, comptable)
        print("done")
        return mult

    def makeinverse(self):
        invdetection = self.multiplicationtable == 0
        values, inverse = torch.max((invdetection.to(torch.int)), 1)
        return inverse

    def makeinversetable(self):
        gl = self.gtlength
        p = self.p
        tablevx = self.grouptable.view(gl, p, 1).expand(gl, p, p)
        yrangevx = arangeic(p).view(1, 1, p).expand(gl, p, p)
        delta = (tablevx == yrangevx).to(torch.int64)
        values, inversetable = torch.max(delta, 1)
        return inversetable

    ##########@ for the list of subgroups ##########

    def subgroupgen(
        self, thesubgroup, thex
    ):  # outputs the subgroup generated by thesubgroup and thex
        currentsubset = torch.zeros(
            (self.gtlength), dtype=torch.bool, device=Dvc
        )
        currentsubset[thesubgroup] = True
        currentsubset[thex] = True
        for i in range(1000):
            currentlength = currentsubset.to(torch.int).sum(0).clone()
            cl2 = currentlength * currentlength
            # print("current length",itp(currentlength))
            mtcurrent1 = self.multiplicationtable[currentsubset]
            mtcurrent1p = mtcurrent1.permute(1, 0)
            mtcurrent2 = mtcurrent1p[currentsubset]
            mtcurrent2vx = mtcurrent2.view(1, cl2).expand(self.gtlength, cl2)
            grouparangevx = (
                arangeic(self.gtlength)
                .view(self.gtlength, 1)
                .expand(self.gtlength, cl2)
            )
            products = (grouparangevx == mtcurrent2vx).any(1)
            currentsubset = currentsubset | products
            newlength = currentsubset.to(torch.int).sum(0)
            if newlength == currentlength:
                # print("break")
                break
        return currentsubset

    def findsubgroup(self, thesubgroup):
        currentsglist = self.subgroup[0 : self.sglistlength, :]
        thesubgroupvx = thesubgroup.view(1, self.gtlength).expand(
            self.sglistlength, self.gtlength
        )
        findsg = (currentsglist == thesubgroupvx).all(1)
        if findsg.any(0):
            assert findsg.to(torch.int).sum(0) == 1
            sgrange = arangeic(self.sglistlength)
            sgnumber = itp(sgrange[findsg][0])
            return True, sgnumber
        else:
            return False, None

    def addnextsubgroup(self):
        for k in range(self.sglistlength):
            thesubgroup = self.subgroup[k]
            # print("try subgroup",k)
            for x in range(self.gtlength):
                if not thesubgroup[x]:
                    # print("try x=",x)
                    sggenx = self.subgroupgen(thesubgroup, x)
                    fsg, sgnumber = self.findsubgroup(sggenx)
                    if not fsg:
                        self.subgroup[self.sglistlength] = sggenx
                        self.sgsize[self.sglistlength] = sggenx.to(
                            torch.int
                        ).sum(0)
                        # print("add subgroup",itp(self.sglistlength),"of length",itp(self.sgsize[self.sglistlength]))
                        self.sglistlength += 1
                        return True
        return False

    def createsubgrouplist(self):
        # the identity
        self.sglistlength = 1
        self.subgroup.masked_fill_(truetensor, False)
        self.sgsize.masked_fill_(truetensor, 0)
        self.sgsize[0] = 1
        self.subgroup[0, 0] = True
        for i in range(self.subgroups_max - 1):
            ansg = self.addnextsubgroup()
            if not ansg:
                break
        print("created a list of", itp(self.sglistlength), "subgroups")
        return

    def findsubgroupbatch(self, batchsize, sgbatch):
        currentsglist = self.subgroup[0 : self.sglistlength, :]
        currentsglistvx = currentsglist.view(
            1, self.sglistlength, self.gtlength
        ).expand(batchsize, self.sglistlength, self.gtlength)
        sgbatchvx = sgbatch.view(batchsize, 1, self.gtlength).expand(
            batchsize, self.sglistlength, self.gtlength
        )
        findsg = (currentsglist == thesubgroupvx).all(2)
        #
        assert (findsg.to(torch.int).sum(1) == 1).all(0)
        #
        sglistarangevx = (
            arangeic(self.sglistlength)
            .view(1, self.sglistlength)
            .expand(batchsize, self.sglistlength)
        )
        sglistarangevxv = sglistarangevx.reshape(batchsize * self.sglistlength)
        findsgv = findsg.reshape(batchsize * self.sglistlength)
        output = sglistarangevxv[findsgv]
        return output

    def makegrouptablebinary(self):
        p = self.p
        gl = self.gtlength
        if p > 7:
            print("warning: not making binary table for p=", itp(p), "> 7")
            return None
        blength = 2 ** p
        brange = arangeic(blength)
        zbinarytable = torch.zeros((blength, p), dtype=torch.bool, device=Dvc)
        for z in range(blength):
            zbinarytable[z, :] = zbinary(p, z)
        gtb = (
            self.grouptable.view(gl, 1, p)
            .expand(gl, blength, p)
            .reshape(gl * blength, p)
        )
        brange = (
            arangeic(blength)
            .view(1, blength, 1)
            .expand(gl, blength, p)
            .reshape(gl * blength, p)
        )
        #
        gtb_mod = zbinarytable[brange, gtb]
        #
        gt_binaryv = binaryzbatch(gl * blength, p, gtb_mod)
        gt_binary = gt_binaryv.view(gl, blength)
        # print("made group table binary")
        return gt_binary
