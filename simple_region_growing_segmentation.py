'''Run a python-based version of the Slicer "Simple Region Growing Segmentation
strategy, which uses ConfidenceConnectedImageFilter followed by
CurvatureFlowImageFilter. I found the defaults in both ITK and Slicer to be
silly, so they're set more sensibly here. More complete documentation is
availiable through ITK.'''

import sys
import argparse
import itk

IMG_UC = itk.Image[itk.UC, 3]  # pylint: disable=no-member
IMG_F = itk.Image[itk.F, 3]  # pylint: disable=no-member

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
    parser.add_argument('--seed', nargs=3, type=int,
                        help="An initial point (in voxel ids) at a 'hint' as" +
                        " to where to begin segmentation.")
    parser.add_argument('--debug', action="store_true", default=False,
                        help="Debug mode. Pipeline stages are computed" +
                        "stepwise, additional output is produced.")
    parser.add_argument('-o', '--output', default=None,
                        help="The segmented file to output")

    args = parser.parse_args(argv[1:])

    # We only take one argument, but argparse puts it in a list with len == 1
    args.image = args.image[0]

    # Build a output filename from args.image
    if args.output is None:
        ext = args.image[args.image.rfind('.'):]
        args.output = args.image.rstrip(ext) + "-label" + ext

    # pylint: disable=global-variable-undefined
    global DEBUG
    DEBUG = args.debug

    return args


def attach_smooth(pipe, iterations, timestep):
    '''Attach a CurvatureFlowImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-name-in-module,no-member
    from itk import CurvatureFlowImageFilter

    cfif = CurvatureFlowImageFilter[IMG_F, IMG_F].New()

    cfif.SetNumberOfIterations(iterations)
    cfif.SetTimeStep(timestep)

    cfif.SetInput(pipe.GetOutput())

    return cfif


def attach_converter(pipe, type_in, type_out):
    '''Attach a CastImageFilter to convert from one itk image type to
    another.'''
    # pylint: disable=no-name-in-module
    from itk import CastImageFilter

    conv = CastImageFilter[type_in, type_out].New()

    conv.SetInput(pipe.GetOutput())

    return conv


def attach_connect(pipe, iterations, stddevs, neighborhood, seed):
    '''Attach a ConfidenceConnectedImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-name-in-module, no-member
    from itk import ConfidenceConnectedImageFilter

    ccif = ConfidenceConnectedImageFilter[IMG_UC, IMG_UC].New()

    ccif.AddSeed(seed)
    ccif.SetNumberOfIterations(iterations)
    ccif.SetMultiplier(stddevs)
    ccif.SetInitialNeighborhoodRadius(neighborhood)

    ccif.SetInput(pipe.GetOutput())

    return ccif


def get_reader(fname):
    '''Initialize a filter pipeline by building an ImageFileReader based on
    the given file 'fname'.'''
    from itk import ImageFileReader  # pylint: disable=no-name-in-module

    reader = ImageFileReader[IMG_F].New()

    reader.SetFileName(fname)

    reader.Update()

    return reader


def attach_writer(pipe, fname):
    '''Initialize and attach an ImageFileWriter to the end of a filter pipeline
    to write out the result.'''
    from itk import ImageFileWriter  # pylint: disable=no-name-in-module

    writer = ImageFileWriter[IMG_UC].New()

    writer.SetInput(pipe.GetOutput())
    writer.SetFileName(fname)

    return writer


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    # pylint: disable=no-member

    args = process_command_line(argv)

    pipe = get_reader(args.image)

    pipe = attach_connect(pipe,
                          args.connect_iterations,
                          args.connect_stddevs,
                          args.connect_neighborhood,
                          args.seed)
    pipe = attach_converter(pipe, IMG_UC, IMG_F)
    pipe = attach_smooth(pipe,
                         args.smooth_iterations,
                         args.smooth_timestep)
    pipe = attach_converter(pipe, IMG_F, IMG_UC)

    pipe = attach_writer(pipe, args.output)

    # run the pipeline
    pipe.Update()

    return

if __name__ == "__main__":
    sys.exit(main(sys.argv))
