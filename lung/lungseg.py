from __future__ import print_function
import sys
import argparse
import SimpleITK as sitk  # pylint: disable=F0401

import matplotlib
import numpy as np

def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument("--dicomdirs", nargs="+",
                        help="The arguments the script operates on.")

    args = parser.parse_args(argv[1:])

    return args


def load_dicom(dirname):
    '''Build an sitk image out of a dicom directory.'''
    reader = sitk.ImageSeriesReader()

    dicom_names = reader.GetGDCMSeriesFileNames(dirname)
    reader.SetFileNames(dicom_names)

    return reader.Execute()


def otsu(img):
    import numpy as np

    array = sitk.GetArrayFromImage(img)
    minval = np.min(array)

    frac_minval = np.count_nonzero(array == minval) / float(array.size)

    filt = sitk.OtsuThresholdImageFilter()

    if frac_minval > .1:
        mask = np.logical_not(array == minval)
        mask = mask.astype('uint8')

        filt.SetMaskValue(1)
        filt.SetMaskOutput(False)

        mask = sitk.GetImageFromArray(mask)
        mask.CopyInformation(img)

        return filt.Execute(img, mask)
    else:
        return filt.Execute(img)


def dialate(img):
    filt = sitk.BinaryDilateImageFilter()
    filt.SetKernelType(filt.Ball)
    filt.SetKernelRadius(3)

    return filt.Execute(img, 0, 1, False)


def find_components(img):
    import numpy as np

    array = sitk.GetArrayFromImage(img)

    bg_fixed = array == array[0, 0, 0]
    bg_fixed = bg_fixed.astype(array.dtype)

    new_img = sitk.GetImageFromArray(bg_fixed)
    new_img.CopyInformation(img)

    filt = sitk.ConnectedComponentImageFilter()
    return filt.Execute(new_img)


def dump(img, name):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigCanvas

    figure = Figure()
    canvas = FigCanvas(figure)

    nplot = 9
    for i in range(1, nplot+1):
        ax = figure.add_subplot(3, 3, i)  # pylint: disable=C0103
        ax.imshow(sitk.GetArrayFromImage(img)[i*img.GetDepth()/(nplot+1)])

    canvas.print_figure(name)


def isolate_lung_field(img):
    '''Isolate the lung field only by taking the largest object that is not
    the chest wall (identified as 0 due to Otsu filtering) or outside air
    (identified by appearing at the border).'''

    array = sitk.GetArrayFromImage(img)

    counts = np.bincount(np.ravel(array))

    outside = array[0, 0, 0]
    chest_wall = 0

    themax = (0, 0)
    for (obj_index, count) in enumerate(counts):
        if obj_index in [outside, chest_wall]:
            continue
        elif count > themax[1]:
            themax = (obj_index, count)

    lung_only = np.array(array == themax[0], dtype=array.dtype)
    lung_only = sitk.GetImageFromArray(lung_only)
    lung_only.CopyInformation(img)

    return lung_only


def isolate_not_biggest(img):

    array = sitk.GetArrayFromImage(img)

    counts = np.bincount(np.ravel(array))

    big = np.argmax(counts)

    not_big = np.array(array != big, dtype=array.dtype)
    not_big = sitk.GetImageFromArray(not_big)
    not_big.CopyInformation(img)

    return not_big


def distribute_seeds(img, n=100):
    import random

    array = sitk.GetArrayFromImage(img)

    print(array.shape)

    seeds = list()
    while len(seeds) < n:
        (z, y, x) = [random.randrange(0, i) for i in array.shape]

        print("Trying", (x, y, z))

        if array[z, y, x] != 0 and (z, y, x) not in seeds:
            print("Accepted!")
            seeds.append((z, y, x))

    return seeds


def checkdist(seeds):
    dists = {}

    for (i, seed) in enumerate(seeds):
        for oseed in seeds[i+1:]:
            dist = sum([(seed[k] - oseed[k])**2
                        for k in range(len(seed))])**0.5

            dists[(seed, oseed)] = dist

    return mindists


def lungseg(img):
    '''Segment lung.'''
    img = otsu(img)
    img = find_components(img)
    img = isolate_lung_field(img)
    img = dialate(img)
    img = find_components(img)
    img = isolate_not_biggest(img)

    return img

def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's sislent and just exposes methods.'''
    args = process_command_line(argv)

    import numpy as np

    for dicomdir in args.dicomdirs:
        img = load_dicom(dicomdir)

        img = lungseg(img)

        seeds = distribute_seeds(img, 5)

        out = sitk.ImageFileWriter()
        out.SetFileName('out.nii')
        out.Execute(img)

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
