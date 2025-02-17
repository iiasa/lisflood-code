"""

Copyright 2019 European Union

Licensed under the EUPL, Version 1.2 or as soon they will be approved by the European Commission  subsequent versions of the EUPL (the "Licence");

You may not use this work except in compliance with the Licence.
You may obtain a copy of the Licence at:

https://joinup.ec.europa.eu/sites/default/files/inline-files/EUPL%20v1_2%20EN(1).txt

Unless required by applicable law or agreed to in writing, software distributed under the Licence is distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the Licence for the specific language governing permissions and limitations under the Licence.

"""
from __future__ import absolute_import, print_function

import numpy as np

from lisflood.global_modules.errors import LisfloodError

from ..global_modules.add1 import loadmap
from ..global_modules.settings import MaskInfo, LisSettings
from . import HydroModule


class riceirrigation(HydroModule):
    """
    # ************************************************************
    # ***** Rice irrigation   ************************************
    # ************************************************************
    """
    input_files_keys = {'riceIrrigation': ['RiceFlooding', 'RicePercolation', 'RicePlantingDay1',
                                           'RiceHarvestDay1', 'RicePlantingDay2', 'RiceHarvestDay2']}
    module_name = 'RiceIrrigation'

    def __init__(self, riceirrigation_variable):
        self.var = riceirrigation_variable

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------

    def initial(self):
        """ initial part of the rice irrigation module
        """
        maskinfo = MaskInfo.instance()
        self.var.PaddyRiceWaterAbstractionFromSurfaceWaterM3 = maskinfo.in_zero()
        settings = LisSettings.instance()
        option = settings.options
        if option['riceIrrigation']:
            if not option['wateruse']:
                # flag with an error message and STOP:
                # riceIrrigation ON MUST HAVE wateruse option ON
                msg = "riceIrrigation module ON MUST HAVE wateruse option ON in setting file"
                raise LisfloodError(msg)

            # ************************************************************
            # ***** PADDY RICE IRRIGATION AND ABSTRACTION ******************
            # ************************************************************

            # Additional water for paddy rice cultivation is calculated seperately, as well as additional open water evaporation from rice fields
            self.var.RiceFlooding = loadmap('RiceFlooding')
            # 10 mm for 10 days (total 10cm water)
            self.var.RicePercolation = loadmap('RicePercolation')
            # FAO: percolation for heavy clay soils: PERC = 2 mm/day

            self.var.RicePlantingDay1 = loadmap('RicePlantingDay1')
            # starting day (of the year) of first rice planting
            self.var.RiceHarvestDay1 = loadmap('RiceHarvestDay1')
            # starting day (of the year) of first rice harvest

            self.var.RicePlantingDay2 = loadmap('RicePlantingDay2')
            # starting day (of the year) of second rice planting
            self.var.RiceHarvestDay2 = loadmap('RiceHarvestDay2')
            # starting day (of the year) of 2nd rice harvest

    def dynamic(self):
        """ dynamic part of the rice irrigation routine
           inside the water abstraction routine
        """
        settings = LisSettings.instance()
        option = settings.options
        maskinfo = MaskInfo.instance()
        if option['riceIrrigation']:
            veg = "Rainfed_prescribed" # ONCE RICE IS SIMULATED IN EPIC, THIS MODULE SHOULD BE SKIPPED WHEN EPIC IS ON!
            iveg, ilanduse, _ = self.var.get_landuse_and_indexes_from_vegetation_GLOBAL(veg)
 
            # water needed for paddy rice is assumed to consist of:
            # phase 1: field preparation: soil saturation (assumed to happen in 10 days, 20 days before planting)
            # phase 2: flood fields (assumed to happen in 10 days, 10 days before planting)
            # phase 3: planting, while keep constant water level during growing season (open water evaporation)
            # phase 4: stop keeping constant water level 20 days before harvest date
            # phase 5: start draining 10 days before harvest date
            
            # ORIGINAL
            #RiceSoilSaturationDemandM3 = (self.var.WS1[ilanduse] - self.var.W1[iveg] + self.var.WS2[ilanduse] - self.var.W2[iveg]) * self.var.RiceFraction * self.var.MMtoM3 * self.var.DtDay
            # this part is using the whole other fraction to calculate the demand -> an rice only soil part is needed
            # RiceIrrigationDemandM3 unit is m3 per time interval [m3/dt]
            
            # EDITED on Jan 15th 2022: saturation demand is computed considering only soil layers 1a and 1b (NO 2)
            RiceSoilSaturationDemandM3 = (self.var.WS1.values[ilanduse] - self.var.W1.values[iveg]) * self.var.RiceFraction * self.var.MMtoM3 * self.var.DtDay
            # this part is using the whole other fraction to calculate the demand -> an rice only soil part is needed
            # RiceIrrigationDemandM3 unit is m3 per time interval [m3/dt]            

            pl_20 = self.var.RicePlantingDay1 - 20
            pl_20 = np.where(pl_20 < 0, 365 + pl_20, pl_20)
            pl_10 = self.var.RicePlantingDay1 - 10
            pl_10 = np.where(pl_10 < 0, 365 + pl_10, pl_10)

            ha_20 = self.var.RiceHarvestDay1 - 20
            ha_20 = np.where(ha_20 < 0, 365 + ha_20, ha_20)
            ha_10 = self.var.RiceHarvestDay1 - 10
            ha_10 = np.where(ha_10 < 0, 365 + ha_10, ha_10)
            
 
            # for Europe ok, but for Global planting can be on the 330 and harvest on the 90, so harvest < planting
            # or riceplanting = 5 => riceplanting -20 =350 ==> riceplanting < riceplanting -20

            """ phase 1: field preparation: soil saturation (assumed to happen in 10 days, 20 days before planting)"""
            RiceSoilSaturationM3 = np.where((self.var.CalendarDay >= pl_20) & (self.var.CalendarDay < pl_10),
                                            0.1 * RiceSoilSaturationDemandM3, maskinfo.in_zero())

            RiceEva = np.maximum(self.var.EWRef - (self.var.ESAct.values[iveg] + self.var.Ta.values[iveg]), 0)            
            RiceEvaporationDemandM3 = RiceEva * self.var.RiceFraction * self.var.MMtoM3  # m3 per time interval
            # should not happen, but just to be sure that this doesnt go <0
            # part of the evaporation is already taken out in soil module!
            # substracting the soil evaporation and transpiration which was already taken off in the soil module
            
            RiceFloodingDemandM3 = self.var.RiceFlooding * self.var.RiceFraction * self.var.MMtoM3 * self.var.DtDay  # m3 per time interval

            """ phase 2: flood fields (assumed to happen in 10 days, 10 days before planting)"""

            RiceFloodingM3 = np.where(
                (self.var.CalendarDay >= pl_10) & (self.var.CalendarDay < self.var.RicePlantingDay1),
                RiceFloodingDemandM3 + RiceEvaporationDemandM3, maskinfo.in_zero())  # m3 per time interval
            # part of the evaporation is already taken out in soil module!
            # assumption is that a fixed water layer is kept on the rice fields, totalling RiceFlooding*10 in mmm (typically 50 or 100 mm)
            # application is spread out over 10 days
            # open water evaporation at the same time

            """ phase 3: planting, while keep constant water level during growing season (open water evaporation) """
            RiceEvaporationM3 = np.where(
                (self.var.CalendarDay >= self.var.RicePlantingDay1) & (self.var.CalendarDay < ha_20),
                RiceEvaporationDemandM3, maskinfo.in_zero())  # m3 per time interval
            # substracting the soil evaporation which was already taken off in the soil module (also transpitation should be tyaken off )

            RicePercolationDemandM3 = self.var.RicePercolation * self.var.RiceFraction * self.var.MMtoM3 * self.var.DtDay  # m3 per time interval         
            RicePercolationM3 = np.where(
                (self.var.CalendarDay >= self.var.RicePlantingDay1) & (self.var.CalendarDay < ha_20),
                RicePercolationDemandM3, maskinfo.in_zero())  # m3 per time interval
            # FAO: percolation for heavy clay soils: PERC = 2 mm/day
            
            self.var.PaddyRiceWaterAbstractionFromSurfaceWaterM3 = RiceSoilSaturationM3 + RiceFloodingM3 + RiceEvaporationM3 + RicePercolationM3  # m3 per time interval
            # m3 water needed for paddyrice

            """# phase 4: stop keeping constant water level 20 days before harvest date
                 phase 5: start draining 10 days before harvest date"""
            # RiceDrainageM3=if((CalendarDay ge (RiceHarvestDay1-10)) and (CalendarDay le RiceHarvestDay1),(WS1-WFC1+WS2-WFC2)*RiceFraction*MMtoM3,0)

            # ORIGINAL: DRAINAGE from all the soil layers
            #RiceDrainageDemandM3 = (self.var.WS1[ilanduse] - self.var.WFC1[ilanduse] + self.var.WS2[ilanduse] - \
            #   self.var.WFC2[ilanduse]) * self.var.RiceFraction * self.var.MMtoM3 * self.var.DtDay  # m3 per time interval
            
            # EDITED on January 15th 2022: DRAINAGE from layers 1a and 1b (NO 2)    
            RiceDrainageDemandM3 = (self.var.WS1.values[ilanduse] - self.var.WFC1.values[ilanduse]) * self.var.RiceFraction * self.var.MMtoM3 * self.var.DtDay  # m3 per time interval    
            
            RiceDrainageM3 = np.where(
                (self.var.CalendarDay >= ha_10) & (self.var.CalendarDay < self.var.RiceHarvestDay1),
                0.1 * RiceDrainageDemandM3, maskinfo.in_zero())

            # drainage until FC to soil/groundwater at end of season
            # assumption that the last weeks before harvest the 50mm water layer is completely evaporating
            # needs to be transported to channel system or being drained

            self.var.UZ.values[iveg][:] += np.where(self.var.SoilFraction.values[iveg] > 0.0,
                                       (RiceDrainageM3 + RicePercolationM3) * self.var.M3toMM / self.var.SoilFraction.values[iveg], ## OtherFraction
                                       0.0)
            # drained water is added to Upper Zone
            