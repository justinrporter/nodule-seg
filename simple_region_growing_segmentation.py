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

    parser.add_argument("images", nargs="+",
                        help="The image that should be segmented.")
    parser.add_argument("--connect_iterations", type=int, default=5,
                        help="The number of iterations to run" +
                             " ConfidenceConnectedImageFilter")
    parser.add_argument('--connect_stddevs', type=float, default=4.0,
                        help="The number of voxel property standard devs " +
                        "to consider as connected.")
    parser.add_argument('--connect_neighborhood', type=int, default=1,
                        help='the number of local pixels around the seed to ' +
                        'use as the start of the calculation.')
    parser.add_argument("--smooth_iterations", default=25, type=long,
                        help="The number of iterations to run" +
                             " CurvatureFlowImageFilter")
    parser.add_argument('--smooth_timestep', default=0.01, type=float,
                        help="The step size used by CurvatureFlowImageFilter")
    parser.add_argument('--seeds', type=str,
                        help="A list of files initial points in JSON format.")
    parser.add_argument('--sigma', default=1.0, type=float,
                        help="The stddev in units of image spacing for the " +
                             "GradientMagnitudeRecursiveGaussianImageFilter.")
    parser.add_argument('-p', '--path', default=None,
                        help="The segmented file to output")
    parser.add_argument('--label', default="autolabel",
                        help="The label to add to each file.")

    args = parser.parse_args(argv[1:])

    import json
    with open(args.seeds) as f:
        seeds = json.loads(f.read())
    args.seeds = seeds

    return args


def input2output(fname, label):
    '''Build output filename from input filename.'''
    ext = fname[fname.rfind('.'):]
    new_fname = fname.rstrip(ext) + "-" + label + ext

    return new_fname


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    import os.path
    import datetime

    args = process_command_line(argv)

    print "Segmenting", len(args.images), "images"

    for fname in args.images:
        basefname = os.path.basename(fname)
        sys.stdout.write("Segmenting " + basefname + "... ")
        sys.stdout.flush()
        start = datetime.datetime.now()

        pipe = itk_attach.FileReader(fname)

        pipe = itk_attach.AnisoDiffStage(pipe,
                                         args.smooth_timestep,
                                         args.smooth_iterations)

        pipe = itk_attach.GradMagRecGaussStage(pipe, args.sigma)

        pipe = itk_attach.ConfidenceConnectStage(pipe,
                                                 args.seeds[basefname],
                                                 args.connect_iterations,
                                                 args.connect_stddevs,
                                                 args.connect_neighborhood)

        pipe = itk_attach.FileWriter(pipe, input2output(fname, args.label))

        # run the pipeline
        pipe.execute()
        print "took", datetime.datetime.now() - start

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
