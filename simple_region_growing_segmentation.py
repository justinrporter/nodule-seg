'''Run a python-based version of the Slicer "Simple Region Growing Segmentation
strategy, which uses ConfidenceConnectedImageFilter followed by
CurvatureFlowImageFilter. I found the defaults in both ITK and Slicer to be
silly, so they're set more sensibly here. More complete documentation is
availiable through ITK.'''

import sys
import argparse
import itk


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser()

    parser.add_argument("image", nargs=1,
                        help="The image that should be segmented.")
    parser.add_argument("--connect_iterations", nargs=1, type=int, default=10,
                        help="The number of iterations to run" +
                             " ConfidenceConnectedImageFilter")
    parser.add_argument('--connect_stddevs', nargs=1, type=float, default=2.0,
                        help="The number of voxel property standard devs " +
                        "to consider as connected.")
    parser.add_argument('--connect_neighborhood', nargs=1, type=int, default=1,
                        help='the number of local pixels around the seed to ' +
                        'use as the start of the calculation.')
    parser.add_argument("--smooth_iterations", nargs=1, default=10, type=int,
                        help="The number of iterations to run" +
                             " CurvatureFlowImageFilter")
    parser.add_argument('--smooth_timestep', nargs=1, default=0.01, type=float,
                        help="The step size used by CurvatureFlowImageFilter")

    args = parser.parse_args(argv[1:])

    return args


def run_smooth(img, iterations, timestep):
    '''Run ConfidenceConnectedImageFilter on the given image input.'''
    return img


def run_connect(img, iterations, stddevs, neighborhood):
    '''Run CurvatureFlowImageFilter on the given image input.'''
    return img


def load(fname):
    '''Load the given image using the itk ImageIOFactory.'''
    img_io = itk.ImageIOFactory.CreateImageIO(fname,
                                              itk.ImageIOFactory.ReadMode)

    return img_io


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    img = load(args.image)

    img = run_connect(img,
                      args.connect_iterations,
                      args.connect_stddevs,
                      args.connect_neighborhood)
    img = run_smooth(img,
                     args.smooth_iterations,
                     args.smooth_timestep)

    print img

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
