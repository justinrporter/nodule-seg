'''Run a python-based segmentation using a geodesic active contour level set
algorithm.'''

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
    parser.add_argument('--seed', nargs=3, type=int,
                        help="An initial point (in voxel ids) at a 'hint' as" +
                        " to where to begin segmentation.")
    parser.add_argument('-o', '--output', default=None,
                        help="The segmented file to output")
    parser.add_argument('--sigma', default=1.0, type=float,
                        help="The stddev in units of image spacing for the " +
                             "GradientMagnitudeRecursiveGaussianImageFilter.")
    parser.add_argument('--alpha', default=1.0, type=float,
                        help="Alpha ('A') parameter in sigmoid filter. Obeys" +
                        " the expression exp((-x+B)/A). Gain.")
    parser.add_argument('--beta', default=0.0, type=float,
                        help="Beta ('B') parameter in sigmoid filter. Obeys" +
                        " the expression exp((-x+B)/A). Zero adjustment.")
    parser.add_argument('--propagation_scaling', default=1.0,
                        help="The weight on propagation force in level set " +
                        "segmentation.")
    parser.add_argument('--geodesic_iterations', default=10, type=int,
                        help="The number of iterations by the " +
                        "GeodesicActiveContourLevelSetImageFilter")

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

    pipe = itk_attach.FileReader(args.image)
    pipe = itk_attach.AnisoDiffStage(pipe)
    pipe = itk_attach.GradMagRecGaussStage(pipe, args.sigma)
    pipe = itk_attach.SigmoidStage(pipe, args.alpha, args.beta)

    pipe2 = itk_attach.FileReader(args.image)
    pipe2 = itk_attach.FastMarchingStage(pipe2)

    pipe = itk_attach.GeoContourLSetStage(pipe2, pipe,
                                          args.propagation_scaling,
                                          args.geodesic_iterations)

    # run the pipeline
    pipe.execute()

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
