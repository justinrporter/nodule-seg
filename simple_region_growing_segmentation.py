'''Run a python-based version of the Slicer "Simple Region Growing Segmentation
strategy, which uses ConfidenceConnectedImageFilter followed by
CurvatureFlowImageFilter. I found the defaults in both ITK and Slicer to be
silly, so they're set more sensibly here. More complete documentation is
availiable through ITK.'''

import sys
import argparse
import itk_attach


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument("image", nargs=1,
                        help="The image that should be segmented.")
    parser.add_argument("--connect_iterations", type=int, default=10,
                        help="The number of iterations to run" +
                             " ConfidenceConnectedImageFilter")
    parser.add_argument('--connect_stddevs', type=float, default=2.0,
                        help="The number of voxel property standard devs " +
                        "to consider as connected.")
    parser.add_argument('--connect_neighborhood', type=int, default=1,
                        help='the number of local pixels around the seed to ' +
                        'use as the start of the calculation.')
    parser.add_argument("--smooth_iterations", default=10, type=long,
                        help="The number of iterations to run" +
                             " CurvatureFlowImageFilter")
    parser.add_argument('--smooth_timestep', default=0.01, type=float,
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

    return args


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    # pylint: disable=no-member

    args = process_command_line(argv)

    pipe = itk_attach.get_reader(args.image)

    pipe = itk_attach.attach_flow_smooth(pipe,
                                         args.smooth_iterations,
                                         args.smooth_timestep)

    pipe = itk_attach.attach_connect(pipe,
                                     args.connect_iterations,
                                     args.connect_stddevs,
                                     args.connect_neighborhood,
                                     args.seed)
    pipe = itk_attach.attach_writer(pipe, args.output)

    # run the pipeline
    pipe.Update()

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
