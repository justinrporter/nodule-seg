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
    parser.add_argument('--seed', nargs=3, type=int,
                        help="An initial point (in voxel ids) at a 'hint' as" +
                        " to where to begin segmentation.")
    parser.add_argument('--debug', action="store_true", default=False,
                        help="Debug mode. Pipeline stages are computed" +
                        "stepwise, additional output is produced.")

    args = parser.parse_args(argv[1:])

    # We only take one argument, but argparse puts it in a list with len == 1
    args.image = args.image[0]

    # Build a output filename from args.image
    ext = args.image[args.image.rfind('.'):]
    args.out_image = args.image.rstrip(ext) + "-label" + ext

    # pylint: disable=global-variable-undefined
    global DEBUG
    DEBUG = args.debug

    return args


def attach_smooth(pipe, iterations, timestep):
    '''Attach a CurvatureFlowImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-member
    image_type = itk.Image[itk.UC, 3]

    cfif = itk.ConfidenceConnectedImageFilter[image_type, image_type].New()

    cfif.SetNumberOfIterations(iterations)
    cfif.SetTimestep(timestep)

    cfif.setInput(pipe.GetOutput())

    if DEBUG:
        cfif.Update()

    return cfif


def attach_connect(pipe, iterations, stddevs, neighborhood, seed):
    '''Attach a ConfidenceConnectedImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-member
    image_type = itk.Image[itk.UC, 3]

    ccif = itk.ConfidenceConnectedImageFilter[image_type, image_type].New()

    ccif.AddSeed(seed)
    ccif.SetNumberOfIterations(iterations)
    ccif.SetMultiplier(stddevs)
    ccif.SetInitialNeighborhoodRadius(neighborhood)

    ccif.SetInput(pipe.GetOutput())

    if DEBUG:
        ccif.Update()

    return ccif


def attach_reader(fname):
    '''Initialize a filter pipeline by building an ImageFileReader based on
    the given file 'fname'.'''
    # pylint: disable=no-member
    image_type = itk.Image[itk.UC, 3]

    reader = itk.ImageFileReader[image_type].New()
    reader.SetFileName(fname)

    if DEBUG:
        reader.DebugOn()
        reader.Update()

    return reader


def attach_writer(pipe, fname):
    '''Initialize and attach an ImageFileWriter to the end of a filter pipeline
    to write out the result.'''
    # pylint: disable=no-member
    image_type = itk.Image[itk.UC, 3]

    writer = itk.ImageFileWriter[image_type].New()

    writer.setInput(pipe.GetOutput())
    writer.SetFileName(fname)

    if DEBUG:
        writer.Update()

    return writer


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    pipe = attach_reader(args.image[0])

    pipe = attach_connect(pipe,
                          args.connect_iterations,
                          args.connect_stddevs,
                          args.connect_neighborhood,
                          args.seed)
    # img = run_smooth(img,
    #                  args.smooth_iterations,
    #                  args.smooth_timestep)

    pipe = attach_writer(pipe, args.out_image)

    # run the pipeline
    pipe.Update()

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
