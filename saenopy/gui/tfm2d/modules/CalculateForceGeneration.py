import numpy as np
from qtpy import QtWidgets
from tifffile import imread
try:
    from scipy.ndimage import binary_fill_holes
except ImportError:
    from scipy.ndimage.morphology import binary_fill_holes
from typing import List, Tuple

from saenopy.gui.common import QtShortCuts
from saenopy.gui.common.gui_classes import CheckAbleGroup
from saenopy.gui.common.code_export import get_code

from .result import Result2D
from .PipelineModule import PipelineModule

from saenopy.pyTFM.TFM_functions import strain_energy_points, contractillity
from saenopy.pyTFM.grid_setup_solids_py import interpolation  # a simple function to resize the mask


class ForceGeneration(PipelineModule):

    def __init__(self, parent=None, layout=None):
        super().__init__(parent, layout)
        self.parent = parent
        #layout.addWidget(self)
        #with self.parent.tabs.createTab("Forces") as self.tab:
        #    pass

        with QtShortCuts.QVBoxLayout(self) as layout:
            layout.setContentsMargins(0, 0, 0, 0)
            with CheckAbleGroup(self, "force generation").addToLayout() as self.group:
                with QtShortCuts.QVBoxLayout():
                    self.label = QtWidgets.QLabel("draw a mask with the red color to select the area where deformations and tractions that are generated by the colony.").addToLayout()
                    self.label.setWordWrap(True)
                    self.input_button = QtShortCuts.QPushButton(None, "calculate force generation", self.start_process)

        self.setParameterMapping("force_gen_parameters", {})

    def valueChanged(self):
        if self.check_available(self.result):
            im = imread(self.result.reference_stack).shape
            #voxel_size1 = self.result.stacks[0].voxel_size
            #stack_deformed = self.result.stacks[0]
            #overlap = 1 - (self.input_element_size.value() / self.input_win.value())
            #stack_size = np.array(stack_deformed.shape)[:3] * voxel_size1 - self.input_win.value()
            #self.label.setText(
            #    f"""Overlap between neighbouring windows\n(size={self.input_win.value()}µm or {(self.input_win.value() / np.array(voxel_size1)).astype(int)} px) is choosen \n to {int(overlap * 100)}% for an element_size of {self.input_element_size.value():.1f}μm elements.\nTotal region is {stack_size}.""")
        else:
            self.label.setText("")

    def check_available(self, result):
        return result.tx is not None

    def check_evaluated(self, result: Result2D) -> bool:
        return result.tx is not None

    def tabChanged(self, tab):
        pass

    def process(self, result: Result2D, force_gen_parameters: dict): # type: ignore
        print("process")
        print("a")
        x = result.mask == 1
        print(result.mask)
        print(x.dtype, x.shape)
        print("x")
        mask = binary_fill_holes(result.mask == 1)  # the mask should be a single patch without holes
        # changing the masks dimensions to fit to the deformation and traction fields
        print("a")
        mask = interpolation(mask, dims=result.u.shape)
        print("a")
        ps1 = result.pixel_size  # pixel size of the image of the beads
        # dimensions of the image of the beads
        print("b")
        ps2 = ps1 * np.mean(np.array(result.shape) / np.array(result.u.shape))  # pixel size of the deformation field
        print("c")
        # strain energy:
        # first we calculate a map of strain energy
        energy_points = strain_energy_points(result.u, result.v, result.tx, result.ty, ps1, ps2)  # J/pixel
        print("d")
        #plt.imsave("strain_energy.png", energy_points)
        #plt.imsave("mask.png", mask)
        # then we sum all energy points in the area defined by mask
        strain_energy = np.sum(energy_points[mask])  # 2.14*10**-13 J
        print("e")
        # contractility
        contractile_force, proj_x, proj_y, center = contractillity(result.tx, result.ty, ps2, mask)  # 2.03*10**-6 N
        print("f")
        result.res_dict["contractility"] = contractile_force
        result.res_dict["area Traction Area"] = np.sum(mask) * ((result.pixel_size * 10 ** -6) ** 2)
        result.res_dict["strain energy"] = strain_energy
        result.res_dict["center of object"] = center
        print("a")
        result.save()

    def get_code(self) -> Tuple[str, str]:
        import_code = "from saenopy.pyTFM.TFM_functions import strain_energy_points, contractillity\nfrom scipy.ndimage import binary_fill_holes\nfrom pyTFM.grid_setup_solids_py import interpolation\n"

        results: List[Result2D] = []
        def code():  # pragma: no cover
            # iterate over all the results objects
            for result in results:
                result.get_mask()
                mask = binary_fill_holes(result.mask == 1)  # the mask should be a single patch without holes
                # changing the masks dimensions to fit to the deformation and traction fields
                mask = interpolation(mask, dims=result.u.shape)

                ps1 = result.pixel_size  # pixel size of the image of the beads
                # dimensions of the image of the beads
                ps2 = ps1 * np.mean(
                    np.array(result.shape) / np.array(result.u.shape))  # pixel size of the deformation field

                # strain energy:
                # first we calculate a map of strain energy
                energy_points = strain_energy_points(result.u, result.v, result.tx, result.ty, ps1, ps2)  # J/pixel

                # then we sum all energy points in the area defined by mask
                strain_energy = np.sum(energy_points[mask])  # 2.14*10**-13 J

                # contractility
                contractile_force, proj_x, proj_y, center = contractillity(result.tx, result.ty, ps2,
                                                                           mask)  # 2.03*10**-6 N

                result.res_dict["contractility"] = contractile_force
                result.res_dict["area Traction Area"] = np.sum(mask) * ((result.pixel_size * 10 ** -6) ** 2)
                result.res_dict["strain energy"] = strain_energy
                result.res_dict["center of object"] = center

                result.save()

        data = {}

        code = get_code(code, data)

        return import_code, code
