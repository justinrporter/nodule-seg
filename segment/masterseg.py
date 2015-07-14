import sys
import argparse
import os
import datetime
import json

import SimpleITK as sitk
import numpy as np

import sitkstrats


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "images", nargs="+",
        help="The dicom directories to operate on.")
    parser.add_argument(
        "--nseeds", type=int, default=10,
        help="The number of randomly placed seeds to produce.")
    parser.add_argument(
        '--media_root', default="media_root/",
        help="The directory to store temporary and intermediate media output")
    parser.add_argument(
        '--profile', default=False, action='store_true',
        help="Run cProfile on script execution.")

    args = parser.parse_args(argv[1:])
    args.media_root = os.path.abspath(args.media_root)
    args.images = [os.path.abspath(image) for image in args.images]

    return args


def set_label(fname, label, labsep='-'):
    '''Set the label (a string addition of labsep + label) for this filename.
    '''
    ext = fname[fname.rfind('.'):]
    fname = fname[:fname.rfind('.')]+labsep+label+ext
    return fname


def opthash(options):
    '''Produce a short hash of the input options.'''
    import hashlib

    sha = hashlib.sha1()
    sha.update(str(options))

    return sha.hexdigest()[0:8]


def mediadir_log(func, (in_img, in_opts), mediadir, sha):
    '''Write the input file in the appropriate directory using its sha'''
    optha = opthash(in_opts)
    label = func.__name__

    (img, opts) = func(in_img, in_opts)

    out_fname = os.path.join(mediadir, label, sha+"-"+optha+'.nii')

    sitkstrats.write(img, out_fname)

    opts['file'] = out_fname

    return (img, opts)


def configure_strats():
    '''
    Construct a dictionary that represents the configuration of all
    segmentation strategies to be used in the script using command line
    arguments. CURRENTLY ACCEPTS NO INPUT.
    '''

    strats = {
        'confidence_connected': {
            'seed-independent': {
                'strategy': sitkstrats.curvature_flow,
                'opts': {'curvature_flow': {
                            'timestep': 0.01,
                            'iterations': 25}}
                },
            'seed-dependent': {
                'strategy': sitkstrats.confidence_connected,
                'opts': {'conf_connect': {'iterations': 2,
                                          'multiplier': 1.5,
                                          'neighborhood': 1},
                         'dialate': {'radius': 1}}
                },
        },
        'geodesic': {
            'seed-independent': {
                'strategy': sitkstrats.aniso_gauss_sigmo,
                'opts': {"anisodiff": {'timestep': 0.01,
                                       'conductance': 9.0,
                                       'iterations': 50},
                         "gauss": {'sigma': 1.5},
                         "sigmoid": {'alpha': -20,
                                     'beta': 50}},
            },
            'seed-dependent': {
                'strategy': sitkstrats.fastmarch_seeded_geocontour,
                'opts': {"geodesic": {"propagation_scaling": 2.0,
                                      "iterations": 300,
                                      "curvature_scaling": 1.0,
                                      "max_rms_change": 1e-7},
                         "seed_shift": 3}
            }
        },
        'watershed': {
            'seed-independent': {
                'strategy': sitkstrats.aniso_gauss_watershed,
                'opts': {"anisodiff": {'timestep': 0.01,
                                       'conductance': 9.0,
                                       'iterations': 50},
                         "gauss": {'sigma': 1.5},
                         "watershed": {"level": 4}}
            },
            'seed-dependent': {
                'strategy': sitkstrats.isolate_watershed,
                'opts': {}
            }
        }
    }

    return strats


def seeddep(imgs, seeds, root_dir, sha, segstrats, lung_size):

    # pick an image, basically at random, from imgs to initialize an array
    # that tracks which areas of the image have already been segmented out
    segmented = np.zeros(sitk.GetArrayFromImage(  # pylint: disable=E1101
        imgs.values()[0]).shape)

    out_info = {}

    for seed in seeds:
        try:
            if segmented[seed[2], seed[1], seed[0]] >= 2:
                print "ALREADY SEGMENTED", seed
        except IndexError as e:
            print seed, segmented.shape
            raise e

        # We want to hold onto images and info dicts for each segmentation,
        # and we want to automagically store the info we put in seed_info into
        # out_info for returning later => use setdefault
        out_imgs = {}
        seed_info = out_info.setdefault("-".join([str(k) for k in seed]), {})

        # for each strategy we want to segment with, get its name and the
        # function that executes it.
        for (sname, strat) in [(strnam, segstrats[strnam]['seed-dependent'])
                               for strnam in segstrats]:
            print sname

            img_in = imgs[sname]

            opts = dict(strat['opts'])
            opts['seed'] = seed

            (tmp_img, tmp_info) = mediadir_log(strat['strategy'],
                                               (img_in, opts),
                                               root_dir,
                                               sha)

            out_imgs[sname] = tmp_img
            seed_info[sname] = tmp_info

        # we need the names of the input files so that our options hash is
        # dependent on the input images.
        consensus_input_files = [s['file'] for s in seed_info.values()]

        try:
            (consensus, consensus_info) = mediadir_log(
                sitkstrats.segmentation_union,
                (out_imgs.values(),
                 {'threshold': 2.0/3.0,
                  'max_size': lung_size * 0.5,
                  'min_size': lung_size * 0,
                  'input_files': consensus_input_files}),
                root_dir,
                sha)
        except RuntimeWarning as w:
            print w
            print "Failure on", seed
            seed_info['consensus'] = "failure"

        segmented += sitk.GetArrayFromImage(consensus)

        seed_info['consensus'] = consensus_info

    return out_info


def run_img(img, sha, nseeds, root_dir):  # pylint: disable=C0111
    '''Run the entire protocol on a particular image starting with sha hash'''
    img_info = {}

    lung_img, lung_info = mediadir_log(sitkstrats.segment_lung,
                                       (img, {}),
                                       root_dir, sha)
    img_info['lungseg'] = lung_info

    segstrats = configure_strats()
    seed_indep_imgs = {}
    seed_indep_info = {}

    for (sname, strat) in [(strnam, segstrats[strnam]['seed-independent'])
                           for strnam in segstrats]:

        try:
            optha = opthash(strat['opts'])
            fname = os.path.join(root_dir, strat['strategy'].__name__,
                                 sha + "-" + optha + ".nii")
            tmp_img = sitkstrats.read(fname)
            tmp_info = strat['opts']
            tmp_info['file'] = os.path.join(fname)
            print "loaded indep_img"
        except RuntimeError:
            print "building "
            (tmp_img, tmp_info) = mediadir_log(strat['strategy'],
                                               (img, strat['opts']),
                                               root_dir,
                                               sha)
            print "built in", tmp_info['time']

        seed_indep_imgs[sname] = tmp_img
        seed_indep_info[sname] = tmp_info

    seeds = sitkstrats.distribute_seeds(lung_img, nseeds)

    # seeds.append((171, 252, 96))
    seeds.append((350, 296, 34))

    seg_info = seeddep(seed_indep_imgs, seeds,
                       root_dir, sha, segstrats, img_info['lungseg']['size'])

    img_info['noduleseg'] = {}
    for seed in seg_info:
        for segstrat in seg_info[seed]:
            combined_info = {'seed-dependent': seg_info[seed][segstrat]}

            if segstrat in seed_indep_info:
                combined_info['seed-independent'] = seed_indep_info[segstrat]

            img_info['noduleseg'].setdefault(
                seed, {})[segstrat] = combined_info

    return img_info


class DateTimeEncoder(json.JSONEncoder):  # pylint: disable=C0111

    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return str(obj)
        elif isinstance(obj, datetime.timedelta):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    run_info = {}

    for img in args.images:
        basename = os.path.basename(img)
        sha = basename[:basename.rfind('.')]

        run_info[sha] = run_img(sitkstrats.read(img), sha,
                                args.nseeds, args.media_root)

    with open("masterseg-run.json", 'w') as f:
        try:
            json_out = json.dumps(run_info, sort_keys=True,
                                  indent=2, separators=(',', ': '),
                                  cls=DateTimeEncoder)
        except TypeError as e:
            print "Error encountered, dumping info"
            print run_info
            raise e

        f.write(json_out)
    return 1


if __name__ == "__main__":
    if "--profile" in sys.argv:
        import cProfile
        sys.exit(cProfile.runctx("main(sys.argv)", globals(),
                                 {"sys.argv": sys.argv}))
    else:
        sys.exit(main(sys.argv))